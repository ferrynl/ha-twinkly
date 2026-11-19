from pathlib import Path
import unittest

from PIL import Image

from app import PRODUCT_PHOTO_KEYS


class ProductPhotoTests(unittest.TestCase):
    def test_all_product_photos_are_transparent(self):
        directory = Path(__file__).with_name("product_photos")
        self.assertEqual({path.stem for path in directory.glob("*.png")}, PRODUCT_PHOTO_KEYS)
        for key in sorted(PRODUCT_PHOTO_KEYS):
            with self.subTest(key=key), Image.open(directory / f"{key}.png") as photo:
                self.assertEqual(photo.mode, "RGBA")
                alpha = photo.getchannel("A")
                self.assertEqual(alpha.getpixel((0, 0)), 0)
                self.assertGreaterEqual(alpha.getextrema()[1], 224)
