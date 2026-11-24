import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from app import ingress_only
from modules.security_center import credentials_check, dependencies, local_checks, parse_version
from modules.update_status import STABLE_CONFIG, UpdateStatus, compare


class SecurityCenterTest(unittest.IsolatedAsyncioTestCase):
    async def test_local_controls_use_real_middleware_and_inspect_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            keyfile = directory / "light-providers.json"
            checks = await local_checks(ingress_only, directory)
            self.assertEqual([row["result"] for row in checks], ["pass"] * 5 + ["not_configured"])
            keyfile.write_text("not read")
            keyfile.chmod(0o600)
            self.assertEqual(credentials_check(keyfile), "pass")
            keyfile.chmod(0o644)
            self.assertEqual(credentials_check(keyfile), "fail")

    def test_dependency_inventory_compares_installed_with_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            lockfile = Path(temp) / "requirements.lock"
            lockfile.write_text('twinkly-test==2.0\nwindows-only==1.0 ; platform_system == "Windows"\n')
            with patch("modules.security_center.platform.system", return_value="Linux"), \
                 patch("modules.security_center.metadata.version", return_value="1.0") as installed:
                self.assertEqual(dependencies(lockfile), [
                    {"name": "twinkly-test", "expected": "2.0", "installed": "1.0"}
                ])
                installed.assert_called_once_with("twinkly-test")

    async def test_update_check_reports_partial_failure_and_reuses_cache(self):
        async def releases(session, url, limit):
            if url == STABLE_CONFIG:
                return b'version: 2.0.1\n'
            if url.endswith('/unreachable/json'):
                raise TimeoutError
            return b'{"info":{"version":"3.0","requires_python":">=3.13","yanked":false}}'

        packages = [{"name": "example", "installed": "2.0"},
                    {"name": "unreachable", "installed": "1.0"}]
        checker = UpdateStatus(parse_version, "3.12.9")
        with patch("modules.update_status.fetch_bytes", AsyncMock(side_effect=releases)) as fetch:
            report = await checker.check("2.0.0", packages)
            self.assertEqual(report["app"], {"latest": "2.0.1", "result": "update"})
            self.assertEqual([row["result"] for row in report["packages"]], ["incompatible_python", "unavailable"])
            self.assertEqual(await checker.check("2.0.0", packages), report)
            self.assertEqual(fetch.await_count, 3)

    def test_version_sorting_does_not_offer_prereleases_or_downgrades(self):
        self.assertEqual(compare("1.10", "1.9")["result"], "ahead")
        self.assertEqual(compare("1.0", "1.0.0")["result"], "current")
        self.assertEqual(compare("1.9", "2.0rc1")["result"], "unavailable")
