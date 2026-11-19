import asyncio
import json
import ssl
import unittest
from unittest.mock import AsyncMock
from modules.common import lan_ip, rgb, brightness
from modules.hue import Hue, xy_color
from modules.govee import Govee, packet

class Validation(unittest.TestCase):
    def test_lan(self):
        self.assertEqual(lan_ip("192.168.1.10"),"192.168.1.10")
        for value in ("127.0.0.1","8.8.8.8","169.254.1.1","example.com"):
            with self.assertRaises(ValueError): lan_ip(value)
    def test_rgb(self):
        for value in ([256,0,0],[True,0,0],[0,0]):
            with self.assertRaises(ValueError): rgb(value)
    def test_brightness(self):
        for value in (0,101,True):
            with self.assertRaises(ValueError): brightness(value)
    def test_hue_xy(self):
        color=xy_color([255,0,0])
        self.assertGreater(color["x"],color["y"])
        self.assertLessEqual(sum(color.values()),1)
    def test_hue_tls(self):
        with self.assertRaises(ValueError): Hue("192.168.1.10","key",ssl._create_unverified_context())
    def test_packet(self):
        self.assertEqual(json.loads(packet("turn",{"value":1})),{"msg":{"cmd":"turn","data":{"value":1}}})

class Commands(unittest.IsolatedAsyncioTestCase):
    async def test_hue(self):
        provider=Hue("192.168.1.10","key",ssl.create_default_context())
        provider.request=AsyncMock()
        await provider.control("12345678-1234-1234-1234-123456789abc",on=True,level=30)
        provider.request.assert_awaited_once_with("PUT","light/12345678-1234-1234-1234-123456789abc",{"on":{"on":True},"dimming":{"brightness":30}})
    async def test_govee(self):
        provider=Govee("192.168.1.11")
        provider.send=AsyncMock()
        await provider.color([1,2,3])
        provider.send.assert_awaited_once_with("colorwc",{"color":{"r":1,"g":2,"b":3},"colorTemInKelvin":0})
