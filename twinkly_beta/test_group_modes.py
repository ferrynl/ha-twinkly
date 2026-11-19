import unittest
from types import SimpleNamespace
from app import Controller

class GroupModes(unittest.TestCase):
    def setUp(self):
        self.controller = Controller.__new__(Controller)
        self.controller.devices = {
            "a": SimpleNamespace(row={"leds":2}, layout={"points":[[0,0,0,0],[1,1,1,0]]}, native_group=None),
            "b": SimpleNamespace(row={"leds":2}, layout={"points":[[0,1,1,0],[1,0,0,0]]}, native_group=None),
        }

    def test_sync(self):
        self.assertEqual(self.controller.group_mapping("a", ["a","b"], "sync"), (0,357))
        self.assertEqual(self.controller.group_mapping("b", ["a","b"], "sync"), (357,0))

    def test_join(self):
        a,b = self.controller.devices.values()
        a.native_group = {"role":"master","offset":0}
        b.native_group = {"role":"slave","offset":2}
        a.layout = {"points":[[0,0,0,0],[1,1,1,0],[2,.75,0,0],[3,.25,1,0]]}
        self.assertEqual(self.controller.group_mapping("b",["a","b"],"join"),(270,90))

    def test_join_missing(self):
        with self.assertRaises(ValueError):
            self.controller.group_mapping("a",["a","b"],"join")

    def test_area(self):
        self.assertEqual(self.controller.group_mapping("b",["a","b"],"area",matrix=True),(357,18))

    def test_join_coordinates_match_renderer(self):
        a,b = self.controller.devices.values()
        a.native_group = {"role":"master","offset":0}
        b.native_group = {"role":"slave","offset":2}
        a.layout = {"points":[[0,0,0,0],[1,1,1,0],[2,.75,0,0],[3,.25,1,0]]}
        b.layout = None
        self.assertEqual(self.controller.group_coordinates("b",["a","b"],"join"),((.75,0,0),(.25,1,0)))
        self.assertEqual(self.controller.group_mapping("b",["a","b"],"join"),(270,90))
