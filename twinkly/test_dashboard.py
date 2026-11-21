"""Verify the dashboard and music GIF routes in the built add-on."""
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from app import Controller, MUSIC_STYLES, asset_path, delete_asset, read_asset, write_asset


class AssetStorageTest(unittest.TestCase):
    def test_atomic_replace_and_delete(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            asset = asset_path(root, "preview.gif")
            write_asset(asset, b"first")
            with patch("app.os.fsync", side_effect=OSError("sync failed")):
                with self.assertRaises(OSError):
                    write_asset(asset, b"second")
            self.assertEqual(read_asset(asset, 5), b"first")
            self.assertEqual(list(root.iterdir()), [asset])
            write_asset(asset, b"second")
            self.assertEqual(read_asset(asset, 6), b"second")
            with self.assertRaises(web.HTTPNotFound):
                read_asset(asset, 5)
            delete_asset(asset)
            delete_asset(asset)
            delete_asset(root / "missing" / asset.name)
            self.assertFalse(asset.exists())

    def test_read_rejects_symlinks_at_open(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.gif"
            source.write_bytes(b"asset")
            previews = root / "previews"
            previews.mkdir()
            asset = asset_path(previews, "preview.gif")
            asset.symlink_to(source)
            with self.assertRaises(web.HTTPNotFound):
                read_asset(asset, 5)

            asset.unlink()
            asset.write_bytes(b"asset")
            moved = root / "archive"
            previews.rename(moved)
            previews.symlink_to(moved, target_is_directory=True)
            with self.assertRaises(web.HTTPNotFound):
                read_asset(asset, 5)


class DashboardSmokeTest(unittest.IsolatedAsyncioTestCase):
    async def test_health_and_ingress(self):
        application = Controller.__new__(Controller).app()
        application.cleanup_ctx.clear()
        async with TestClient(TestServer(application)) as client:
            async with client.get("/healthz") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.text(), "OK")
            async with client.get("/") as response:
                self.assertEqual(response.status, 403)

    async def test_bundled_wordmark(self):
        application = Controller.__new__(Controller).app()
        application.middlewares.clear()
        application.cleanup_ctx.clear()
        async with TestClient(TestServer(application)) as client:
            async with client.get("/twinkly-wordmark.svg") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.content_type, "image/svg+xml")
                self.assertIn("<svg", await response.text())

    async def test_dashboard_and_music_gallery(self):
        # The test server uses loopback and does not start the live UDP stream.
        controller = Controller.__new__(Controller)
        application = controller.app()
        application.middlewares.clear()
        application.cleanup_ctx.clear()
        async with TestClient(TestServer(application)) as client:
            async with client.get("/") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                html = await response.text()
                self.assertIn('id="music-style-grid"', html)
                self.assertIn("function renderMusicGallery", html)
            for style in sorted(MUSIC_STYLES):
                with self.subTest(style=style):
                    async with client.get(f"/music-demo/{style}") as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.content_type, "image/gif")
                        payload = await response.read()
                    with Image.open(io.BytesIO(payload)) as gif:
                        self.assertEqual(gif.size, (300, 320))
                        self.assertGreater(gif.n_frames, 1)
            async with client.get("/music-demo/unknown") as response:
                self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()
