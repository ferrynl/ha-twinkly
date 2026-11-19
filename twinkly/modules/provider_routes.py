"""Ingress-protected provider endpoints. No credentials in responses."""
import asyncio
from aiohttp import web, ClientError
from .provider_store import ProviderStore
from .hue import Hue
from .hue_pairing import fingerprint
from .hue_discovery import discover as hue_discover
from .govee_discovery import discover as govee_discover
from .profiles import govee_profile

def install(app, store=None):
    store=store or ProviderStore()
    scanners={"hue":hue_discover,"govee":govee_discover}
    scan_lock=asyncio.Lock()
    async def configured(request):
        try:
            return web.json_response(store.public())
        except (ValueError,OSError):
            return web.json_response({"error":"configuration_unavailable"},status=503)
    async def scan(request):
        provider=request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        if scan_lock.locked():
            return web.json_response({"error":"scan_busy"},status=409)
        async with scan_lock:
            try:
                found=await scanners[provider]()
                return web.json_response({"devices":found,"verified":False})
            except (OSError,ValueError,TimeoutError):
                return web.json_response({"error":"discovery_failed"},status=503)
    async def inventory(request):
        provider=request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        try:
            records=store.load()[provider]
        except (ValueError,OSError):
            return web.json_response({"error":"configuration_unavailable"},status=503)
        results=[]
        for identifier,record in records.items():
            if provider=="govee":
                results.append({"id":identifier,"address":record["address"],"status":"unknown"})
                continue
            try:
                client=Hue(record["address"],record["application_key"],fingerprint(record["certificate_sha256"]))
                results.append({"id":identifier,"lights":await client.profiles(),"status":"online"})
            except (ClientError,TimeoutError,ValueError,OSError,RuntimeError):
                results.append({"id":identifier,"status":"unavailable","lights":[]})
        return web.json_response({"devices":results})
    app.router.add_get("/providers/configured",configured)
    app.router.add_post("/providers/{provider}/discover",scan)
    app.router.add_get("/providers/{provider}/inventory",inventory)
