import unittest
from modules.hue_pairing import fingerprint, pairing_result, pair

class HuePairingTests(unittest.TestCase):
    def test_pin(self):
        self.assertEqual(fingerprint("ab"*32).fingerprint,bytes.fromhex("ab"*32))
    def test_bad_pin(self):
        for value in (None,"ab"*16,"zz"*32,"ab"*33):
            with self.subTest(value=value), self.assertRaises(ValueError): fingerprint(value)
    def test_success(self):
        self.assertEqual(pairing_result([{"success":{"username":"abcdefghij","clientkey":"ab"*16}}]),{"application_key":"abcdefghij","client_key":"ab"*16})
    def test_button(self):
        with self.assertRaises(PermissionError): pairing_result([{"error":{"type":101}}])
    def test_other_error(self):
        with self.assertRaises(RuntimeError): pairing_result([{"error":{"type":1,"description":"secret"}}])
    def test_malformed(self):
        for value in (None,{},[],[None],[{}],[{"success":{"username":"short"}}],[{"success":{"username":"abcdefghij","clientkey":"bad"}}]):
            with self.subTest(value=value), self.assertRaises(ValueError): pairing_result(value)

class PairNetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_invalid_ip(self):
        with self.assertRaises(ValueError): await pair("8.8.8.8","ab"*32)
    async def test_invalid_pin(self):
        with self.assertRaises(ValueError): await pair("192.168.1.2","bad")
