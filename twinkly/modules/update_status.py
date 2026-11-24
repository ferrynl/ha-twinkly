"""Read-only update discovery from fixed public release sources."""
import asyncio
from datetime import datetime, timezone
import json
from time import monotonic
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout
from packaging.specifiers import SpecifierSet
from packaging.version import Version

STABLE_CONFIG = "https://raw.githubusercontent.com/ferrynl/ha-apps/main/twinkly/config.yaml"
PYPI = "https://pypi.org/pypi/"


async def fetch_bytes(session, url, limit):
    async with session.get(url, allow_redirects=False) as response:
        if response.status != 200:
            raise ValueError("Release source unavailable")
        body = bytearray()
        async for chunk in response.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > limit:
                raise ValueError("Release response too large")
        return bytes(body)


def compare(local, upstream, *, beta=False, requires_python=None, python=None):
    installed = Version(local)
    if not isinstance(upstream, str):
        raise ValueError("Missing published version")
    published = Version(upstream)
    if (published.is_prerelease and not beta) or (beta and (not published.pre or published.pre[0] != "b")):
        return {"latest": None, "result": "unavailable"}
    if published <= installed:
        result = "current" if published == installed else "ahead"
    elif requires_python and python and not SpecifierSet(requires_python).contains(python, prereleases=True):
        result = "incompatible_python"
    else:
        result = "update"
    return {"latest": upstream, "result": result}


class UpdateStatus:
    def __init__(self, parse_version, python):
        self.parse_version = parse_version
        self.python = python
        self.report = None
        self.expires = 0
        self.lock = asyncio.Lock()

    async def check(self, version, packages):
        async with self.lock:
            if self.report is not None and monotonic() < self.expires:
                return self.report
            self.report = await self.collect(version, packages)
            incomplete = (self.report["app"]["result"] == "unavailable"
                          or any(row["result"] == "unavailable" for row in self.report["packages"]))
            self.expires = monotonic() + (300 if incomplete else 3600)
            return self.report

    async def collect(self, version, packages):
        unavailable = {"latest": None, "result": "unavailable"}
        errors = (ClientError, TimeoutError, UnicodeError, ValueError, KeyError, TypeError)
        async with ClientSession(timeout=ClientTimeout(total=6)) as session:
            slots = asyncio.Semaphore(8)

            async def app():
                if not version:
                    return unavailable
                try:
                    source = await fetch_bytes(session, STABLE_CONFIG, 65536)
                    latest = self.parse_version(source.decode("utf-8"))
                    return compare(version, latest)
                except errors:
                    return unavailable

            async def package(row):
                name = row["name"]
                if not row["installed"]:
                    return {"name": name, "latest": None, "result": "not_installed"}
                async with slots:
                    try:
                        source = await fetch_bytes(session, PYPI + quote(name, safe="") + "/json", 16 * 1024 * 1024)
                        info = json.loads(source)["info"]
                        if info.get("yanked"):
                            result = unavailable
                        else:
                            result = compare(row["installed"], info["version"],
                                             requires_python=info.get("requires_python"), python=self.python)
                    except errors:
                        result = unavailable
                return {"name": name, **result}

            latest_app, latest_packages = await asyncio.gather(
                app(), asyncio.gather(*(package(row) for row in (packages or [])))
            )
        return {"app": latest_app, "packages": latest_packages, "packages_checked": packages is not None,
                "checked_at": datetime.now(timezone.utc).isoformat()}
