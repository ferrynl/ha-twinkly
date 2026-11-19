"""Local mDNS discovery; advertisements are untrusted until TLS pairing."""
import asyncio
import math
import re
from .common import lan_ip

SERVICE = "_hue._tcp.local."

def candidate(name, addresses, properties):
    raw = properties.get(b"bridgeid", b"")
    if not isinstance(raw, bytes):
        return None
    bridge_id = raw.decode("ascii", errors="ignore")
    if not re.fullmatch(r"[0-9a-fA-F]{16}", bridge_id):
        return None
    ips = set()
    for address in addresses:
        try:
            ips.add(lan_ip(address))
        except (ValueError, TypeError):
            continue
    if not ips:
        return None
    return {"bridge_id":bridge_id.lower(),"name":str(name)[:200],"addresses":sorted(ips),"verified":False}

async def discover(timeout=3):
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not .2 <= timeout <= 10:
        raise ValueError("Discovery timeout must be 0.2 to 10 seconds")
    from zeroconf import IPVersion, ServiceStateChange
    from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser, AsyncServiceInfo
    found = {}
    pending = set()
    names = set()
    async with AsyncZeroconf(ip_version=IPVersion.V4Only) as zc:
        async def resolve(name):
            info = AsyncServiceInfo(SERVICE,name)
            if await info.async_request(zc.zeroconf, 1000):
                item = candidate(name,info.parsed_addresses(),info.properties)
                if item:
                    existing = found.get(item["bridge_id"])
                    if existing:
                        item["addresses"] = sorted(set(existing["addresses"] + item["addresses"]))
                    found[item["bridge_id"]] = item
        def changed(zeroconf, service_type, name, state_change):
            if state_change in (ServiceStateChange.Added,ServiceStateChange.Updated) and name not in names and len(names)<64:
                names.add(name)
                pending.add(asyncio.create_task(resolve(name)))
        browser = AsyncServiceBrowser(zc.zeroconf,SERVICE,handlers=[changed])
        try:
            await asyncio.sleep(timeout)
        finally:
            await browser.async_cancel()
            for task in pending:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*pending,return_exceptions=True)
    return sorted(found.values(),key=lambda item:item["bridge_id"])
