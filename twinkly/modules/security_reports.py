"""Find GitHub container scan reports for the installed release."""
import asyncio
from datetime import datetime, timezone
import json
import re
from time import monotonic
from urllib.parse import urlencode

from aiohttp import ClientError, ClientSession, ClientTimeout

from .update_status import fetch_bytes

ARTIFACTS = "https://api.github.com/repos/ferrynl/ha-apps/actions/artifacts"
REPOSITORY_ID = 1449996400
ARCHITECTURES = {"amd64": "X64", "aarch64": "ARM64"}


def matching_artifacts(payload, name):
    artifacts = payload["artifacts"]
    if not isinstance(artifacts, list):
        raise ValueError("Invalid GitHub artifact listing")
    matches = {}
    for artifact in artifacts:
        run = artifact.get("workflow_run") or {}
        run_id = run.get("id")
        if (artifact.get("name") == name and artifact.get("expired") is False
                and run.get("head_branch") == "main"
                and run.get("head_repository_id") == REPOSITORY_ID
                and type(run_id) is int and run_id > 0):
            matches[run_id] = artifact.get("created_at")
    return matches


class SecurityReports:
    def __init__(self):
        self.report = None
        self.expires = 0
        self.lock = asyncio.Lock()

    async def check(self, version):
        async with self.lock:
            if self.report and self.report["version"] == version and monotonic() < self.expires:
                return self.report
            self.report = await self.collect(version)
            complete = all(row["result"] == "available" for row in self.report["reports"])
            self.expires = monotonic() + (3600 if complete else 300)
            return self.report

    async def collect(self, version):
        checked = datetime.now(timezone.utc).isoformat()
        rows = {arch: {"architecture": arch, "result": "unavailable"} for arch in ARCHITECTURES}
        if version and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-beta\.[0-9]+)?", version):
            async with ClientSession(timeout=ClientTimeout(total=6), headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "Christmas-Control-Center",
            }) as session:
                async def lookup(arch):
                    name = f"christmas-control-center-{version}-{ARCHITECTURES[arch]}-security"
                    query = urlencode({"name": name, "per_page": 20})
                    try:
                        payload = json.loads(await fetch_bytes(session, f"{ARTIFACTS}?{query}", 256 * 1024))
                        matches = matching_artifacts(payload, name)
                    except (ClientError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
                        return {}
                    rows[arch]["result"] = "not_found"
                    return matches

                matches = await asyncio.gather(*(lookup(arch) for arch in ARCHITECTURES))
            # Use a common run when available. A report can also be shown while its peer is missing.
            shared = matches[0].keys() & matches[1].keys()
            if shared or any(matches):
                run_id = max(shared or (matches[0].keys() | matches[1].keys()))
                for arch, candidates in zip(ARCHITECTURES, matches):
                    if run_id in candidates:
                        rows[arch].update(result="available", run_id=run_id,
                                          created_at=candidates[run_id])
        return {"version": version, "reports": list(rows.values()), "checked_at": checked}
