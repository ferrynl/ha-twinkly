import unittest
from app import Controller

class PhysicalFrames(unittest.TestCase):
    def test_identification(self):
        for i,rgb in enumerate([(90,0,0),(0,90,0),(0,0,90),(90,90,0)]):
            self.assertEqual(Controller.physical_frame("identify",i,[(0,0,0)]*210,0),bytes(rgb)*210)

    def test_axes(self):
        coords=[(0,1,0),(1,0,0)]
        self.assertEqual(Controller.physical_frame("horizontal",0,coords,0),bytes([90]*3+[0]*3))
        self.assertEqual(Controller.physical_frame("vertical",0,coords,0),bytes([0]*3+[90]*3))

    def test_led_order(self):
        self.assertEqual(Controller.physical_frame("led",0,range(2),.125),bytes([0]*3+[90]*3))

    def test_led_order_starts_at_the_top_without_reordering_the_middle(self):
        forward = [(0,.1,0), (0,.8,0), (0,.5,0), (0,.9,0)]
        for points, top, next_led in ((forward, 0, 1), (forward[::-1], 3, 2)):
            order = Controller.led_test_order(points)
            for elapsed, expected in ((0, top), (.125, next_led)):
                frame = Controller.physical_frame("led", 0, order, elapsed)
                self.assertEqual([i for i in range(4) if frame[3*i]], [expected])
