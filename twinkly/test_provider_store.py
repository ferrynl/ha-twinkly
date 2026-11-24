import unittest
import tempfile
import os
from modules.provider_store import ProviderStore

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store=ProviderStore(self.tmp.name)
        self.data={"version":1,"hue":{"bridge":{"address":"192.168.1.2","application_key":"abcdefghij","client_key":"ab"*16,"certificate_sha256":"ab"*32}},"govee":{}}
    def test_empty(self):
        self.assertEqual(self.store.load(),{"version":1,"hue":{},"govee":{}})
    def test_roundtrip(self):
        self.store.save(self.data)
        self.assertEqual(ProviderStore(self.tmp.name).load(),self.data)
    def test_permissions(self):
        self.store.save(self.data)
        self.assertEqual(self.store.path.stat().st_mode & 0o777,0o600)
    def test_public_redaction(self):
        self.store.save(self.data)
        self.assertEqual(self.store.public(),{"hue":{"bridge":{"address":"192.168.1.2","configured":True}},"govee":{}})
    def test_invalid_save_preserves_previous(self):
        self.store.save(self.data)
        with self.assertRaises(ValueError): self.store.save({})
        self.assertEqual(self.store.load(),self.data)
    def test_public_ip_rejected(self):
        self.data["hue"]["bridge"]["address"]="8.8.8.8"
        with self.assertRaises(ValueError): self.store.save(self.data)
    def test_weak_permissions_rejected(self):
        self.store.save(self.data)
        os.chmod(self.store.path,0o644)
        with self.assertRaises(PermissionError): self.store.load()
    def test_bad_json_rejected(self):
        self.store.save(self.data)
        self.store.path.write_text("bad")
        with self.assertRaises(ValueError): self.store.load()
    def test_symlink_rejected(self):
        target=self.store.path.parent/"target"
        target.write_text("{}")
        self.store.path.symlink_to(target)
        with self.assertRaises(OSError): self.store.load()
