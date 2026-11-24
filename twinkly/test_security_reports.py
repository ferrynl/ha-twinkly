import json
import unittest
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, patch

from modules.security_reports import REPOSITORY_ID, SecurityReports

VERSION = "2.0.0-beta.33"


def artifact(name, run_id, *, branch="main", repository=REPOSITORY_ID, expired=False):
    return {"name": name, "expired": expired, "created_at": "2026-11-21T10:00:00Z",
            "workflow_run": {"id": run_id, "head_branch": branch, "head_repository_id": repository}}


class SecurityReportsTests(unittest.IsolatedAsyncioTestCase):
    async def test_verifies_version_origin_expiry_and_current_pair(self):
        async def fetch(session, url, limit):
            name, = parse_qs(urlsplit(url).query)["name"]
            self.assertTrue(name.startswith(f"christmas-control-center-{VERSION}-"))
            rows = [
                artifact(name, 10),
                artifact(name, 30, branch="feature"),
                artifact(name, 40, repository=900),
                artifact(name, 50, expired=True),
                artifact("other-version", 99),
            ]
            if "X64" in name:
                rows.append(artifact(name, 20))
            return json.dumps({"artifacts": rows}).encode()

        reports = SecurityReports()
        with patch("modules.security_reports.fetch_bytes", side_effect=fetch) as request:
            result = await reports.check(VERSION)
            self.assertEqual(await reports.check(VERSION), result)
            self.assertEqual(request.await_count, 2)
        self.assertEqual(result["version"], VERSION)
        self.assertEqual([(row["architecture"], row["result"], row["run_id"])
                          for row in result["reports"]],
                         [("amd64", "available", 10), ("aarch64", "available", 10)])

    async def test_network_failure_and_missing_report_have_distinct_statuses(self):
        fetch = AsyncMock(side_effect=[TimeoutError(), b'{"artifacts":[]}'])
        with patch("modules.security_reports.fetch_bytes", fetch):
            result = await SecurityReports().check(VERSION)
        self.assertEqual([row["result"] for row in result["reports"]], ["unavailable", "not_found"])

    async def test_missing_or_invalid_beta_avoids_network_requests(self):
        with patch("modules.security_reports.fetch_bytes") as request:
            result = await SecurityReports().check("invalid?name=other")
        request.assert_not_called()
        self.assertEqual([row["result"] for row in result["reports"]], ["unavailable", "unavailable"])
