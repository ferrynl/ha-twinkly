import unittest
from pathlib import Path
from types import SimpleNamespace
from app import Device

class NativeGroupMapping(unittest.TestCase):
    def test_combines_summary_and_sync(self):
        replies = {
            "summary": {"group": {"mode":"slave","uid":"group","name":"Muur"}},
            "led/movie/config": {"sync":{"mode":"slave","master_id":"hardware-master","offset":420,"size":840}},
        }
        d = SimpleNamespace(native_group_until=0, native_group=None, api=replies.__getitem__)
        Device.load_native_group(d)
        self.assertEqual(d.native_group["id"], "group")
        self.assertEqual(d.native_group["offset"], 420)
        self.assertEqual(d.native_group["size"], 840)
        self.assertEqual(d.native_group["master_id"], "hardware-master")

    def test_standalone_summary_does_not_hide_movie_sync_master(self):
        replies = {
            "summary": {"group": {"mode": "none"}},
            "led/movie/config": {"sync": {"mode": "master", "uid": "wall", "size": 840}},
        }
        d = SimpleNamespace(native_group_until=0, native_group=None, api=replies.__getitem__)
        Device.load_native_group(d)
        self.assertEqual(d.native_group["role"], "master")
        self.assertEqual(d.native_group["id"], "wall")
        self.assertEqual(d.native_group["offset"], 0)

    def test_beta_sidebar_name_and_slug(self):
        config = Path(__file__).with_name("config.yaml").read_text(encoding="utf-8").splitlines()
        self.assertIn("name: Christmas Control Center Beta", config)
        self.assertIn("slug: twinkly_kerst_beta", config)
