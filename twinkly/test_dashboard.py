"""Verify the dashboard and music GIF routes in the built add-on."""
import io
import unittest

from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from app import Controller, MUSIC_STYLES


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

    async def test_google_home_assets_are_served_by_the_add_on(self):
        application = Controller.__new__(Controller).app()
        application.middlewares.clear()
        application.cleanup_ctx.clear()
        async with TestClient(TestServer(application)) as client:
            async with client.get("/") as response:
                self.assertIn('src="google-home.js"', await response.text())
            async with client.get("/google-home.js") as response:
                self.assertEqual(response.status, 200)
                self.assertIn("christmas_control_center_demo", await response.text())
            for image in ("google-home-demo.jpg", "google-home-show.jpg"):
                with self.subTest(image=image):
                    async with client.get("/" + image) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.content_type, "image/jpeg")
                        self.assertTrue((await response.read()).startswith(b"\xff\xd8"))

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


class RealtimeRGBTest(unittest.TestCase):
    def test_primary_colors_and_cycle(self):
        from app import PIXELS, live_pattern

        for fps in (5, 20, 25):
            for second, color in ((0, (255, 0, 0)), (3, (0, 255, 0)),
                                  (6, (0, 0, 255)), (9, (255, 0, 0))):
                with self.subTest(fps=fps, second=second):
                    self.assertEqual(live_pattern('rgb-test', second * fps, fps),
                                     bytes(color) * PIXELS)
