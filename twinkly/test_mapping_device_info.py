import unittest
from types import SimpleNamespace
from app import Controller

class MappingDeviceInfo(unittest.TestCase):
    def test_metadata(self):
        d = SimpleNamespace(row={"name":"Muur","leds":210}, product_code="ABC",
                            details={"firmware_version":"2.8.0","hardware_version":"1","token":"secret","ssid":"private"})
        info = Controller.mapping_device_info(d, True)
        self.assertEqual(info["product_code"],"ABC")
        self.assertEqual(info["firmware_version"],"2.8.0")
        self.assertEqual(info["hardware_version"],"1")
        self.assertNotIn("token",info)
        self.assertNotIn("ssid",info)

    def test_offline(self):
        d = SimpleNamespace(row={"name":"Muur","leds":210}, product_code="ABC", details=None)
        info = Controller.mapping_device_info(d, False)
        self.assertEqual(info["metadata_status"],"unavailable")
        self.assertIsNone(info["firmware_version"])
