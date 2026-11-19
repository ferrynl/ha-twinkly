"""Ingress-protected provider endpoints. No credentials in responses."""
import asyncio
import re

from aiohttp import web, ClientError

from .provider_store import ProviderStore
from .hue import Hue
from .hue_pairing import fingerprint, pair, inspect_certificate
from .govee import Govee
from .common import lan_ip
from .hue_discovery import discover as hue_discover
from .govee_discovery import discover as govee_discover, statuses as govee_statuses
from .lighting import Lighting


def install(app, store=None, controller=None):
    store = store or ProviderStore()
    scanners = {"hue": hue_discover, "govee": govee_discover}
    scan_lock = asyncio.Lock()
    mutation_lock = asyncio.Lock()
    clients = {}
    connection_errors = (ClientError, TimeoutError, ValueError, OSError, RuntimeError)

    def adapter(provider, identifier, record):
        key = (provider, identifier)
        cached = clients.get(key)
        if cached and cached[0] == record:
            return cached[1]
        if provider == "hue":
            client = Hue(record["address"], record["application_key"], fingerprint(record["certificate_sha256"]))
        else:
            client = Govee(record["address"])
        clients[key] = (record, client)
        return client

    async def configured(request):
        try:
            return web.json_response(store.public())
        except (ValueError, OSError):
            return web.json_response({"error": "configuration_unavailable"}, status=503)

    async def scan(request):
        provider = request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        if scan_lock.locked():
            return web.json_response({"error": "scan_busy"}, status=409)
        async with scan_lock:
            try:
                found = await scanners[provider]()
                return web.json_response({"devices": found, "verified": False})
            except (OSError, ValueError, TimeoutError):
                return web.json_response({"error": "discovery_failed"}, status=503)

    async def read_inventory(provider, *, reports=False):
        records = store.load()[provider]
        if provider == "govee":
            found = {}
            if reports and records:
                async with scan_lock:
                    try:
                        found = await govee_statuses({row["address"] for row in records.values()})
                    except OSError:
                        pass
            results = []
            for identifier, record in records.items():
                address = record["address"]
                row = {"id": identifier, "address": address, "status": "unknown"}
                if address in found:
                    row["report"] = found[address]
                    row["status"] = "reported"
                results.append(row)
            return results

        async def bridge(identifier, record):
            row = {"id": identifier, "address": record["address"]}
            try:
                lights = await adapter(provider, identifier, record).profiles()
                return dict(row, lights=lights, status="online")
            except connection_errors:
                return dict(row, lights=[], status="unavailable")

        return await asyncio.gather(*(bridge(identifier, record) for identifier, record in records.items()))

    async def inventory(request):
        provider = request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        try:
            return web.json_response({"devices": await read_inventory(provider)})
        except (ValueError, OSError):
            return web.json_response({"error": "configuration_unavailable"}, status=503)

    async def connect(request):
        provider = request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        try:
            body = await request.json()
            identifier = body["id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", identifier):
                raise ValueError()
            address = lan_ip(body["address"])
            async with mutation_lock:
                data = store.load()
                if len(data[provider]) >= 64 and identifier not in data[provider]:
                    raise ValueError()
                record = {"address": address}
                if provider == "hue":
                    pin = body["certificate_sha256"]
                    record.update(await pair(address, pin))
                    record["certificate_sha256"] = pin
                data[provider][identifier] = record
                store.save(data)
                clients.pop((provider, identifier), None)
            return web.json_response({"ok": True})
        except PermissionError:
            return web.json_response({"error": "pairing_permission"}, status=409)
        except (*connection_errors, KeyError, TypeError):
            return web.json_response({"error": "connection_failed"}, status=400)

    async def send(provider, identifier, light_id, action, value):
        async with mutation_lock:
            record = store.load()[provider][identifier]
            client = adapter(provider, identifier, record)
            if provider == "hue":
                field = {"power": "on", "brightness": "level", "color": "color"}[action]
                await client.control(light_id, **{field: value})
            else:
                await {"power": client.power, "brightness": client.dim, "color": client.color}[action](value)

    async def control(request):
        provider = request.match_info["provider"]
        if provider not in scanners:
            raise web.HTTPNotFound()
        try:
            body = await request.json()
            await send(provider, body["id"], body.get("light_id"), body["action"], body["value"])
            return web.json_response({"ok": True, "confirmed": provider == "hue"})
        except (*connection_errors, KeyError, TypeError):
            return web.json_response({"error": "control_failed"}, status=400)

    async def certificate(request):
        if scan_lock.locked():
            return web.json_response({"error": "scan_busy"}, status=409)
        async with scan_lock:
            try:
                body = await request.json()
                address = lan_ip(body["address"])
                pin = await inspect_certificate(address)
                return web.json_response({"certificate_sha256": pin, "verified": False})
            except (ValueError, KeyError, TypeError, OSError, TimeoutError):
                return web.json_response({"error": "certificate_unavailable"}, status=400)

    app.router.add_post("/providers/hue/certificate", certificate)
    app.router.add_post("/providers/{provider}/connect", connect)
    app.router.add_post("/providers/{provider}/control", control)
    app.router.add_get("/providers/configured", configured)
    app.router.add_post("/providers/{provider}/discover", scan)
    app.router.add_get("/providers/{provider}/inventory", inventory)
    if controller is not None:
        async def unified_inventory(provider):
            return await read_inventory(provider, reports=True)

        Lighting(controller, store, unified_inventory, send).install(app.router)
