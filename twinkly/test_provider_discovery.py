import unittest
from modules.govee_discovery import parse_scan, discover
from modules.govee import packet

class ScanTests(unittest.TestCase):
    def test_valid(self):
        d={"ip":"192.168.1.3","device":"AA:BB","sku":"H6159"}
        self.assertEqual(parse_scan(packet("scan",d),("192.168.1.3",4003)),d)
    def test_spoofed(self):
        self.assertIsNone(parse_scan(packet("scan",{"ip":"192.168.1.4","device":"AA","sku":"H1"}),("192.168.1.3",4003)))
    def test_public_source(self):
        self.assertIsNone(parse_scan(packet("scan",{"ip":"8.8.8.8","device":"AA","sku":"H1"}),("8.8.8.8",4003)))
    def test_malformed(self):
        for data in (b"",b"null",b"[]",b"{}",b"\xff",packet("scan",None),packet("turn",{})):
            with self.subTest(data=data):
                self.assertIsNone(parse_scan(data,("192.168.1.3",4003)))
    def test_invalid_identity(self):
        for device in ("",None,123,"x"*129):
            self.assertIsNone(parse_scan(packet("scan",{"ip":"192.168.1.3","device":device,"sku":"H1"}),("192.168.1.3",4003)))

class ScanTimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounds(self):
        for t in (0,-1,11):
            with self.assertRaises(ValueError): await discover(t)
