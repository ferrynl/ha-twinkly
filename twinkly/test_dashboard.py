"""Verify the dashboard and music GIF routes in the built add-on."""
import io
import unittest

from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from app import Controller, MUSIC_STYLES


class DashboardSmokeTest(unittest.IsolatedAsyncioTestCase):
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
