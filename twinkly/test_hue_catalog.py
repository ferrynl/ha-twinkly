import json
from pathlib import Path
import unittest

from PIL import Image


class HueCatalogTests(unittest.TestCase):
    def test_catalog_has_transparent_photos_and_valid_aliases(self):
        directory = Path(__file__).with_name("images") / "HUE"
        index = json.loads((directory / "models.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(index), 1200)
        for model in ("LST002", "LCT015", "LCT024", "LCT026", "LCG002"):
            self.assertIn(model, index)
        names = set(index.values())
        self.assertGreaterEqual(len(names), 500)
        for name in names:
            with self.subTest(photo=name):
                self.assertRegex(name, r"^[A-Za-z0-9_-]{1,64}\.png$")
                with Image.open(directory / name, formats=["PNG"]) as photo:
                    self.assertLessEqual(max(photo.size), 480)
                    low, high = photo.convert("RGBA").getchannel("A").getextrema()
                    self.assertEqual(low, 0)
                    self.assertGreater(high, 0)
