"""Ingress-protected provider endpoints. No credentials in responses."""
import asyncio
from aiohttp import web, ClientError
from .provider_store import ProviderStore
from .hue import Hue
from .hue_pairing import fingerprint, pair
from .govee import Govee
from .common import lan_ip
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
    mutation_lock=asyncio.Lock()
    clients={}
    async def connect(request):
        provider=request.match_info["provider"]
        if provider not in scanners: raise web.HTTPNotFound()
        try:
            body=await request.json()
            identifier=body["id"]
            address=lan_ip(body["address"])
            async with mutation_lock:
                data=store.load()
                if len(data[provider])>=64 and identifier not in data[provider]:
                    raise ValueError("limit")
                record={"address":address}
                if provider=="hue":
                    pin=body["certificate_sha256"]
                    record.update(await pair(address,pin))
                    record["certificate_sha256"]=pin
                data[provider][identifier]=record
                store.save(data)
                clients.pop((provider,identifier),None)
            return web.json_response({"ok":True})
        except PermissionError:
            return web.json_response({"error":"pairing_permission"},status=409)
        except (ValueError,KeyError,TypeError,ClientError,OSError,RuntimeError,TimeoutError):
            return web.json_response({"error":"connection_failed"},status=400)
    async def control(request):
        provider=request.match_info["provider"]
        if provider not in scanners: raise web.HTTPNotFound()
        try:
            body=await request.json()
            identifier=body["id"]
            async with mutation_lock:
                record=store.load()[provider][identifier]
                key=(provider,identifier)
                if key not in clients:
                    clients[key]=Hue(record["address"],record["application_key"],fingerprint(record["certificate_sha256"])) if provider=="hue" else Govee(record["address"])
                client=clients[key]
                action=body["action"]
                if action not in ("power","brightness","color"): raise ValueError("action")
                value=body["value"]
                if provider=="hue":
                    await client.control(body["light_id"],**{ {"power":"on","brightness":"level","color":"color"}[action]:value})
                else:
                    await {"power":client.power,"brightness":client.dim,"color":client.color}[action](value)
            return web.json_response({"ok":True,"confirmed":provider=="hue"})
        except (ValueError,KeyError,TypeError,ClientError,OSError,RuntimeError,TimeoutError):
            return web.json_response({"error":"control_failed"},status=400)
    app.router.add_post("/providers/{provider}/connect",connect)
    app.router.add_post("/providers/{provider}/control",control)
    app.router.add_get("/providers/configured",configured)
    app.router.add_post("/providers/{provider}/discover",scan)
    app.router.add_get("/providers/{provider}/inventory",inventory)
