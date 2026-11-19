import base64
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aiohttp import web
from PIL import Image

from app import BUNDLED_EFFECT_PREVIEWS, Controller, EFFECT_PREVIEWS


class EffectPreviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_gif_keeps_animation_and_follows_movie_uuid(self):
        controller = Controller.__new__(Controller)
        effect = {"kind": "movie", "id": 1, "name": "Peachy", "unique_id": "movie-a"}
        controller.devices = {"lamp": SimpleNamespace(effects=[effect])}
        with tempfile.TemporaryDirectory() as folder, patch("app.IMAGES", Path(folder)):
            frames = [Image.new("RGB", (4, 4), color) for color in ("red", "blue")]
            content = io.BytesIO()
            frames[0].save(content, format="GIF", save_all=True, append_images=frames[1:], duration=100)
            original = content.getvalue()
            path = controller.effect_gif_path("lamp", effect)
            query = {"id": "lamp", "kind": "movie", "index": "1", "ref": path.stem}

            async def body():
                return {"image": base64.b64encode(original).decode()}

            response = await controller.effect_image(SimpleNamespace(query=query, method="POST", json=body))
            self.assertEqual(response.status, 200)
            self.assertEqual(path.read_bytes(), original)
            with Image.open(path) as image:
                self.assertEqual(image.n_frames, 2)

            effect["id"] = 4
            query["index"] = "4"
            self.assertIsInstance(await controller.effect_image(SimpleNamespace(query=query, method="GET")), web.FileResponse)
            effect["unique_id"] = "different-movie"
            with self.assertRaises(web.HTTPNotFound):
                await controller.effect_image(SimpleNamespace(query=query, method="GET"))

    def test_name_prevents_reuse_of_unidentified_movie_slot(self):
        first = {"kind": "movie", "id": 1, "name": "Flare"}
        second = dict(first, name="Showtime")
        self.assertNotEqual(Controller.effect_gif_path("lamp", first), Controller.effect_gif_path("lamp", second))

    def test_all_seven_bundled_effects_are_animated(self):
        self.assertEqual(len(BUNDLED_EFFECT_PREVIEWS), 7)
        self.assertEqual(
            set(BUNDLED_EFFECT_PREVIEWS.values()), {path.name for path in EFFECT_PREVIEWS.glob("*.gif")}
        )
        for name, filename in BUNDLED_EFFECT_PREVIEWS.items():
            with self.subTest(name=name):
                path = Controller.bundled_effect_image({"kind": "movie", "name": name.upper()})
                self.assertEqual(path.name, filename)
                with Image.open(path) as image:
                    self.assertEqual(image.format, "GIF")
                    self.assertGreater(image.n_frames, 1)
                    for frame in range(image.n_frames):
                        image.seek(frame)
                        image.load()
        self.assertIsNone(Controller.bundled_effect_image({"kind": "movie", "name": "Rainbow Plasma"}))
        self.assertIsNone(Controller.bundled_effect_image({"kind": "effect", "name": "Rainbow"}))

    async def test_local_image_overrides_default_and_deletion_restores_default(self):
        controller = Controller.__new__(Controller)
        effect = {"kind": "movie", "id": 1, "name": "  Cotton   Candy  "}
        controller.devices = {"lamp": SimpleNamespace(effects=[effect])}
        with tempfile.TemporaryDirectory() as folder, patch("app.IMAGES", Path(folder)):
            custom = controller.effect_gif_path("lamp", effect)
            query = {"id": "lamp", "kind": "movie", "index": "1", "ref": custom.stem}
            default = await controller.effect_image(SimpleNamespace(query=query, method="GET"))
            self.assertEqual(default._path.name, "cotton-candy.gif")
            custom.write_bytes(default._path.read_bytes())
            override = await controller.effect_image(SimpleNamespace(query=query, method="GET"))
            self.assertEqual(override._path, custom)

            async def body():
                return {"image": None}

            await controller.effect_image(SimpleNamespace(query=query, method="POST", json=body))
            restored = await controller.effect_image(SimpleNamespace(query=query, method="GET"))
            self.assertEqual(restored._path, default._path)
