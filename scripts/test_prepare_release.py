import struct
import tempfile
import unittest
from pathlib import Path

import yaml

from prepare_release import prepare


class PrepareReleaseTest(unittest.TestCase):
    def setUp(self):
        self.source = Path(__file__).resolve().parents[1] / "twinkly"
        self.config = yaml.safe_load((self.source / "config.yaml").read_text(encoding="utf-8"))
        self.version = self.config["version"]
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.target = Path(tmp.name) / "app"

    def test_stable_keeps_identity_and_ports(self):
        prepare(self.source, self.target, self.version)
        for filename in ("config.yaml", "Dockerfile", "DOCS.md", "CHANGELOG.md"):
            self.assertEqual(
                (self.source / filename).read_bytes(), (self.target / filename).read_bytes()
            )

    def test_beta_has_separate_identity_and_ports(self):
        version = f"{self.version}-beta.2"
        prepare(self.source, self.target, version)
        config = yaml.safe_load((self.target / "config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["slug"], "twinkly_kerst_beta")
        self.assertEqual(config["version"], version)
        self.assertEqual(config["boot"], "manual")
        self.assertEqual(config["ingress_port"], 18491)
        self.assertEqual(config["options"], self.config["options"])
        self.assertIn("TWINKLY_HTTP_PORT=18491 TWINKLY_DDP_PORT=18492",
                      (self.target / "Dockerfile").read_text(encoding="utf-8"))
        self.assertTrue((self.target / "CHANGELOG.md").read_text(encoding="utf-8").startswith(f"# {version}\n"))

    def test_store_presentation_for_both_channels(self):
        for suffix, description in (
            ("", "Lokale kerstlichtstudio voor lichtshows, groepen en muziekeffecten."),
            ("-beta.1", "Probeer als eerste nieuwe kerstlichtshows en muziekeffecten."),
        ):
            with self.subTest(channel=suffix):
                target = self.target.with_name(f"app{suffix}")
                prepare(self.source, target, f"{self.version}{suffix}")
                config = yaml.safe_load((target / "config.yaml").read_text(encoding="utf-8"))
                self.assertEqual(config["description"], description)
                self.assertEqual(config["name"], "Christmas Control Center" + (" Beta" if suffix else ""))
                artwork = self.source / "beta_branding" if suffix else self.source
                for filename, size in (("icon.png", (128, 128)), ("logo.png", (500, 200))):
                    data = (target / filename).read_bytes()
                    self.assertEqual(data, (artwork / filename).read_bytes())
                    self.assertEqual(data[:8], bytes.fromhex("89504e470d0a1a0a"))
                    self.assertEqual(struct.unpack(">II", data[16:24]), size)
                intro = (target / "README.md").read_text(encoding="utf-8")
                self.assertIn("LedFX", intro)
                self.assertEqual("vroege toegang" in intro, bool(suffix))
                self.assertFalse((target / "beta_branding").exists())

    def test_rejects_wrong_or_malformed_version(self):
        for version in ("99999.0.0", f"{self.version}-beta.0", "nightly"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                prepare(self.source, self.target, version)
        self.assertFalse(self.target.exists())


if __name__ == "__main__":
    unittest.main()
