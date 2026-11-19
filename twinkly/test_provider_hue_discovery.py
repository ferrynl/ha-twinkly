import unittest
from modules.hue_discovery import candidate, discover
class DiscoveryTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(candidate("Hue",["192.168.1.2"],{b"bridgeid":b"001788FFFE123456"}),{"bridge_id":"001788fffe123456","name":"Hue","addresses":["192.168.1.2"],"verified":False})
    def test_duplicate_addresses(self):
        self.assertEqual(candidate("Hue",["192.168.1.2","192.168.1.2","10.1.1.1"],{b"bridgeid":b"001788FFFE123456"})["addresses"],["10.1.1.1","192.168.1.2"])
    def test_public_address(self):
        self.assertIsNone(candidate("Hue",["8.8.8.8","127.0.0.1","::1"],{b"bridgeid":b"001788FFFE123456"}))
    def test_invalid_ids(self):
        for value in (b"",b"bad",None,b"../",b"0"*17):
            with self.subTest(value=value):
                self.assertIsNone(candidate("Hue",["192.168.1.2"],{b"bridgeid":value}))
    def test_missing_id(self):
        self.assertIsNone(candidate("Hue",["192.168.1.2"],{}))
class TimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_timeout(self):
        for value in (True,0,11,float("nan"),float("inf"),"3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                await discover(value)
