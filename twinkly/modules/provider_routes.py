"""Ingress-protected provider endpoints. No credentials in responses."""
import asyncio
from contextlib import asynccontextmanager
import json
import re

from aiohttp import web, ClientError

from .provider_store import ProviderStore
from .hue import Hue
from .hue_entertainment import EntertainmentError, HueEntertainment
from .hue_pairing import fingerprint, pair, inspect_certificate
from .govee import Govee
from .common import lan_ip
from .hue_discovery import discover as hue_discover
from .govee_discovery import discover as govee_discover, statuses as govee_statuses
from .lighting import Lighting
from .lighting_projects import install as install_projects
from .hue_scene_images import install as install_hue_scene_images, scene_image_path
from .hue_scene_images import install_product_images, product_image_path
from .hue_tests import LampTest, TESTS as HUE_TESTS, test_plan as hue_test_plan
from . import govee_tests
from .govee_cloud import CloudError, install as install_govee_cloud


def install(app, store=None, controller=None, govee_key=None):
    store = store or ProviderStore()
    scanners = {"hue": hue_discover, "govee": govee_discover}
    scan_lock = asyncio.Lock()
    govee_models = {}
    mutation_lock = asyncio.Lock()
    clients = {}
    lighting = None
    collection_lock = asyncio.Lock()
    entertainment = HueEntertainment()
    scene_images = install_hue_scene_images(app, store)
    product_images, catalog_photo = install_product_images(app, store)
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
                if provider == "govee":
                    govee_models.clear()
                    govee_models.update({(row["device"], row["ip"]): row["sku"] for row in found})
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
                row = {"id": identifier, "address": address, "status": "unknown",
                       "sku": govee_models.get((identifier, address)) or record.get("sku")}
                if address in found:
                    row["report"] = found[address]
                    row["status"] = "reported"
                results.append(row)
            return results

        def with_photo(profile):
            model = profile.get("model")
            result = dict(profile)
            try:
                if product_image_path(product_images, model).is_file():
                    result["has_product_image"] = True
            except (ValueError, OSError):
                pass
            if catalog_photo(model) is not None:
                result["has_catalog_image"] = True
            return result

        async def bridge(identifier, record):
            row = {"id": identifier, "address": record["address"]}
            client = adapter(provider, identifier, record)
            try:
                client.last_profiles = await client.profiles()
                return dict(row, lights=[with_photo(profile) for profile in client.last_profiles], status="online")
            except connection_errors:
                lights = [dict(with_photo(profile), status="unavailable") for profile in client.last_profiles]
                return dict(row, lights=lights, status="unavailable")

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
                    if entertainment.active_bridge == identifier:
                        return web.json_response({"error": "hue_bridge_busy"}, status=409)
                    pin = body["certificate_sha256"]
                    record.update(await pair(address, pin))
                    record["certificate_sha256"] = pin
                else:
                    sku = govee_models.get((identifier, address)) or data[provider].get(identifier, {}).get("sku")
                    if sku:
                        record["sku"] = sku
                data[provider][identifier] = record
                store.save(data)
                clients.pop((provider, identifier), None)
                if lighting is not None:
                    lighting.command_snapshot = None
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
                if entertainment.active_bridge == identifier:
                    raise RuntimeError("Hue Entertainment is active on this Bridge")
                field = {"power": "on", "brightness": "level", "color": "color", "temperature": "mirek"}[action]
                await client.control(light_id, **{field: value})
            else:
                await {"power": client.power, "brightness": client.dim, "color": client.color,
                       "temperature": client.temperature}[action](value)

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

    async def hue_collections(request):
        async def bridge(identifier, record):
            row = {"id": identifier, "address": record["address"]}
            try:
                collections = await adapter("hue", identifier, record).collections()
                for collection in collections:
                    for scene in collection["scenes"]:
                        try:
                            path = scene_image_path(scene_images, identifier, scene["id"])
                        except ValueError:
                            continue
                        if path.is_file():
                            scene["has_image"] = True
                return dict(row, collections=collections, status="online")
            except (*connection_errors, KeyError, TypeError):
                return dict(row, collections=[], status="unavailable")

        try:
            records = store.load()["hue"]
        except (ValueError, OSError):
            return web.json_response({"error": "configuration_unavailable"}, status=503)
        return web.json_response({"bridges": await asyncio.gather(
            *(bridge(identifier, record) for identifier, record in records.items())
        )})

    async def control_hue_collection(request):
        try:
            body = await request.json()
            identifier = body["bridge"]
            async with (lighting.control_lock if lighting else collection_lock):
                if entertainment.active_bridge == identifier:
                    return web.json_response({"error": "hue_bridge_busy"}, status=409)
                if lighting:
                    testing = lamp_test.task is not None and not lamp_test.task.done()
                    active = lighting.music.members | ({lamp_test.target} if testing else set())
                    if any(key and json.loads(key)[:2] == ["hue", identifier] for key in active):
                        return web.json_response({"error": "hue_bridge_busy"}, status=409)
                async with mutation_lock:
                    record = store.load()["hue"][identifier]
                    await adapter("hue", identifier, record).control_collection(
                        body["id"], body["action"], body.get("value")
                    )
            return web.json_response({"ok": True})
        except (*connection_errors, KeyError, TypeError):
            return web.json_response({"error": "control_failed"}, status=400)

    async def entertainment_areas(request):
        bridges = await asyncio.gather(*(
            entertainment.areas(identifier, record, adapter("hue", identifier, record))
            for identifier, record in store.load()["hue"].items()
        ))
        return web.json_response({"bridges": bridges, **entertainment.status()})

    async def entertainment_status(request):
        return web.json_response(entertainment.status())

    async def entertainment_control(request):
        try:
            body = await request.json()
            async with (lighting.control_lock if lighting else collection_lock):
                async with mutation_lock:
                    if body["action"] == "stop":
                        if entertainment.music_active:
                            raise EntertainmentError("busy", 409)
                        await entertainment.stop()
                    elif body["action"] == "start":
                        identifier = body["bridge"]
                        if lighting:
                            testing = lamp_test.task is not None and not lamp_test.task.done()
                            active = lighting.music.members | ({lamp_test.target} if testing else set())
                            if any(key and json.loads(key)[:2] == ["hue", identifier] for key in active):
                                raise EntertainmentError("busy", 409)
                        record = store.load()["hue"][identifier]
                        await entertainment.start(identifier, record, adapter("hue", identifier, record),
                                                  body["area"], body["effect"], body["brightness"])
                    else:
                        raise ValueError()
            return web.json_response(entertainment.status())
        except EntertainmentError as error:
            return web.json_response({"error": error.code}, status=error.status)
        except (KeyError, TypeError, ValueError):
            return web.json_response({"error": "invalid_effect"}, status=400)
        except connection_errors:
            return web.json_response({"error": "connection_failed"}, status=503)

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

    @asynccontextmanager
    async def govee_cloud_context(identifier):
        async with (lighting.control_lock if lighting else collection_lock):
            if lighting:
                testing = lamp_test.task is not None and not lamp_test.task.done()
                active = lighting.music.members | ({lamp_test.target} if testing else set())
                target = re.sub(r"[:-]", "", identifier).casefold()
                for key in filter(None, active):
                    parts = json.loads(key)
                    if parts[0] == "govee" and re.sub(r"[:-]", "", parts[1]).casefold() == target:
                        raise CloudError("device_busy", 409)
            async with mutation_lock:
                yield

    install_govee_cloud(app, govee_key, govee_cloud_context, store.path.with_name("govee-cloud-devices.json"))
    app.router.add_get("/providers/hue/entertainment", entertainment_areas)
    app.router.add_get("/providers/hue/entertainment/status", entertainment_status)
    app.router.add_post("/providers/hue/entertainment/control", entertainment_control)
    app.cleanup_ctx.append(entertainment.cleanup)
    app.router.add_get("/providers/hue/collections", hue_collections)
    app.router.add_post("/providers/hue/collections/control", control_hue_collection)
    app.router.add_post("/providers/hue/certificate", certificate)
    app.router.add_post("/providers/{provider}/connect", connect)
    app.router.add_post("/providers/{provider}/control", control)
    app.router.add_get("/providers/configured", configured)
    app.router.add_post("/providers/{provider}/discover", scan)
    app.router.add_get("/providers/{provider}/inventory", inventory)
    if controller is not None:
        async def unified_inventory(provider):
            return await read_inventory(provider, reports=True)

        async def start_hue_music(targets, level):
            if not targets:
                return "no_lights", None, set()
            by_bridge = {}
            for key in sorted(targets):
                _, identifier, light_id = json.loads(key)
                by_bridge.setdefault(identifier, {})[light_id] = key
            state = "missing_area"
            async with mutation_lock:
                try:
                    records = store.load()["hue"]
                except connection_errors:
                    return "connection_failed", None, set()
                for identifier, members in by_bridge.items():
                    record = records.get(identifier)
                    if not record:
                        continue
                    if lamp_test.task and not lamp_test.task.done() and lamp_test.target:
                        if json.loads(lamp_test.target)[:2] == ["hue", identifier]:
                            state = "busy"
                            continue
                    try:
                        covered, area = await entertainment.start_music(
                            identifier, record, adapter("hue", identifier, record),
                            members.keys(), lambda: controller.music_frame(), level,
                        )
                    except EntertainmentError as error:
                        state = error.code
                    except connection_errors:
                        state = "connection_failed"
                    else:
                        return "streaming", area, {members[light_id] for light_id in covered}
            return state, None, set()

        lighting = Lighting(controller, store, unified_inventory, send)
        lighting.music.entertainment = entertainment
        lighting.music.start_hue = start_hue_music
        lighting.install(app.router)
        lamp_test = LampTest()
        lighting.lamp_test = lamp_test

        def test_provider(request):
            brand = request.match_info["brand"]
            if brand not in ("hue", "govee"):
                raise web.HTTPNotFound()
            return brand

        def test_status(brand):
            status = lamp_test.status()
            if status["id"] and json.loads(status["id"])[0] != brand:
                return {"id": None, "test": None, "result": None}
            return status

        async def lamp_test_status(request):
            return web.json_response(test_status(test_provider(request)))

        async def lamp_test_control(request):
            brand = test_provider(request)
            supported = HUE_TESTS if brand == "hue" else govee_tests.TESTS
            try:
                body = await request.json()
                test = body["test"]
                if not isinstance(test, str) or test not in supported | {"stop"}:
                    raise ValueError()
                async with lighting.control_lock:
                    if test == "stop":
                        if test_status(brand)["id"]:
                            await lamp_test.stop()
                        return web.json_response(test_status(brand))
                    key = body["id"]
                    provider, identifier, light_id = json.loads(key)
                    if provider != brand:
                        raise ValueError()
                    if brand == "hue":
                        if entertainment.active_bridge == identifier:
                            return web.json_response({"error": "hue_bridge_busy"}, status=409)
                        if not re.fullmatch(r"[0-9a-fA-F-]{36}", light_id):
                            raise ValueError()
                    elif light_id != identifier:
                        raise ValueError()
                    record = store.load()[brand][identifier]
                    await lamp_test.stop()
                    if key in lighting.music.members:
                        await lighting.music.stop()
                    client = adapter(brand, identifier, record)
                    if brand == "hue":
                        path = "light/" + light_id

                        async def read():
                            resources = await client.request("GET", path)
                            return resources[0] if resources and resources[0].get("id") == light_id else {}

                        async def apply(change):
                            await client.request("PUT", path, change)

                        light = await read()
                        if not light:
                            raise web.HTTPNotFound()
                        changes, restore = hue_test_plan(light, test)
                    else:
                        async def read():
                            async with scan_lock:
                                reports = await govee_statuses({client.address})
                            return govee_tests.test_state(reports.get(client.address, {}))

                        async def apply(change):
                            on = change.get("on", {}).get("on")
                            if on is True:
                                await client.power(True)
                            if "dimming" in change:
                                await client.dim(change["dimming"]["brightness"])
                            if "rgb" in change:
                                await client.color(change["rgb"])
                            if on is False:
                                await client.power(False)

                        changes, restore = govee_tests.test_plan(await read(), test)
                    lamp_test.start(key, test, apply, read, changes, restore)
                return web.json_response(lamp_test.status())
            except (KeyError, TypeError, ValueError):
                raise web.HTTPBadRequest()
            except connection_errors:
                raise web.HTTPServiceUnavailable()

        app.router.add_get("/lighting/{brand:hue|govee}-test", lamp_test_status)
        app.router.add_post("/lighting/{brand:hue|govee}-test", lamp_test_control)
        app.cleanup_ctx.append(lighting.music_cleanup)
        install_projects(app, lighting)
