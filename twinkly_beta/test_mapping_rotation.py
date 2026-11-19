import unittest
from app import Controller

class MappingRotation(unittest.TestCase):
    def test_angles(self):
        for angle, expected in [(0,(0,0)),(90,(1,0)),(180,(1,1)),(270,(0,1))]:
            with self.subTest(angle=angle):
                self.assertEqual(Controller.transform_xy(0,0,{"rotation":angle}),expected)

    def test_mirror(self):
        self.assertEqual(Controller.transform_xy(0,0,{"mirror_x":True}),(1,0))
        self.assertEqual(Controller.transform_xy(0,0,{"mirror_y":True}),(0,1))
