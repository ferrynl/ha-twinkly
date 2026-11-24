"""Optional Govee OpenAPI scenes and segment controls."""
import asyncio
from hashlib import sha256
import json
import re
from time import monotonic
from uuid import uuid4

from aiohttp import ClientError, ClientSession, ClientTimeout, web

from .common import RateGate, rgb
from .provider_store import ProviderStore

BASE = "https://openapi.api.govee.com/router/api/v1"
SEGMENT_TYPE = "devices.capabilities.segment_color_setting"
SCENE_TYPES = {
    ("devices.capabilities.dynamic_scene", "lightScene"),
    ("devices.capabilities.mode", "presetScene"),
}
SEGMENT_ACTIONS = {"color": ("segmentedColorRgb", "rgb"),
                   "brightness": ("segmentedBrightness", "brightness")}
HEADERS = {"Cache-Control": "no-store"}


class CloudError(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


def objects(value):
    return (item for item in value if isinstance(item, dict)) if isinstance(value, list) else ()


def cap_params(capability):
    params = capability.get("parameters")
    return params if isinstance(params, dict) else {}


def segment_spec(capabilities, action):
    instance, field_name = SEGMENT_ACTIONS[action]
    for cap in capabilities:
        if (cap.get("type"), cap.get("instance")) != (SEGMENT_TYPE, instance):
            continue
        fields = {field.get("fieldName"): field for field in objects(cap_params(cap).get("fields"))
                  if isinstance(field.get("fieldName"), str)}
        selector = fields.get("segment", {})
        indices = sorted({option["value"] for option in objects(selector.get("options"))
                          if type(option.get("value")) is int and 0 <= option["value"] <= 255})
        bounds = selector.get("elementRange")
        if not indices and isinstance(bounds, dict):
            low, high = bounds.get("min"), bounds.get("max")
            if type(low) is int and type(high) is int and 0 <= low <= high <= 255:
                indices = list(range(low, high + 1))
        size = selector.get("size") if isinstance(selector.get("size"), dict) else {}
        minimum, limit = size.get("min", 1), size.get("max", len(indices))
        if (not indices or type(minimum) is not int or type(limit) is not int
                or not 1 <= minimum <= min(limit, len(indices)) or field_name not in fields):
            continue
        spec = {"indices": indices, "minimum": minimum, "limit": min(limit, len(indices))}
        if action == "brightness":
            allowed = fields[field_name].get("range")
            if not isinstance(allowed, dict):
                continue
            low, high, step = allowed.get("min"), allowed.get("max"), allowed.get("precision", 1)
            if (type(low) is not int or type(high) is not int or type(step) is not int
                    or not 0 <= low <= high <= 100 or step < 1):
                continue
            spec.update(low=low, high=high, step=step)
        return spec


def scene_options(capabilities):
    found = {}
    for cap in capabilities:
        pair = (cap.get("type"), cap.get("instance"))
        if not all(isinstance(part, str) for part in pair) or pair not in SCENE_TYPES:
            continue
        for option in objects(cap_params(cap).get("options")):
            name, value = option.get("name"), option.get("value")
            if isinstance(name, dict):
                name = name.get("en") or name.get("key")
            if not isinstance(name, str) or not name.strip():
                continue
            if isinstance(value, dict):
                if not all(type(value.get(key)) is int for key in ("paramId", "id")):
                    continue
                value = {key: value[key] for key in ("paramId", "id")}
            elif type(value) is not int:
                continue
            key = sha256(json.dumps([*pair, value], sort_keys=True).encode()).hexdigest()
            found.setdefault(key, (name.strip()[:128], {"type": pair[0], "instance": pair[1], "value": value}))
    return found


class GoveeCloud:
    def __init__(self, key, cache_path=None):
        self.key = key.strip() if isinstance(key, str) and re.fullmatch(r"\s*[\x21-\x7e]{1,128}\s*", key) else ""
        self.device_cache = {}
        self.scene_cache = {}
        self.cache_path = cache_path
        self.account = sha256(self.key.encode()).hexdigest()
        if self.key and cache_path is not None:
            try:
                saved = ProviderStore.read(cache_path, {}, 4 * 1024 * 1024)
                if saved.get("account") == self.account and isinstance(saved.get("devices"), dict):
                    self.device_cache = saved["devices"]
            except (OSError, ValueError, AttributeError, RecursionError):
                pass
        self.lock = asyncio.Lock()
        self.commands = RateGate(.5)

    async def request(self, method, path, payload=None):
        if not self.key:
            raise CloudError("disabled", 409)
        body = {"requestId": uuid4().hex, "payload": payload} if payload is not None else None
        try:
            async with ClientSession(timeout=ClientTimeout(total=7),
                                     headers={"Govee-API-Key": self.key}) as session:
                async with session.request(method, BASE + path, json=body, allow_redirects=False) as response:
                    if response.status != 200:
                        raise self.error(response.status)
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        data.extend(chunk)
                        if len(data) > 2 * 1024 * 1024:
                            raise ValueError("Oversized response")
            result = json.loads(data)
            if result.get("code") != 200:
                raise self.error(result.get("code"))
            return result
        except (ClientError, TimeoutError, ValueError, TypeError, AttributeError, RecursionError):
            raise CloudError("cloud_failed", 502) from None

    @staticmethod
    def error(status):
        if status == 429:
            return CloudError("rate_limited", 429)
        if status in (401, 403):
            return CloudError("key_rejected", 502)
        return CloudError("cloud_failed", 502)

    async def devices(self):
        async with self.lock:
            result = await self.request("GET", "/user/devices")
            if not isinstance(result.get("data"), list):
                raise CloudError("cloud_failed", 502)
            devices = {}
            for item in objects(result["data"]):
                if item.get("type") != "devices.types.light":
                    continue
                identifier, sku, name = item.get("device"), item.get("sku"), item.get("deviceName")
                if (not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", identifier)
                        or not isinstance(sku, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sku)):
                    continue
                devices[identifier] = {"id": identifier, "sku": sku, "name": name[:128] if isinstance(name, str) and name else sku,
                                       "caps": list(objects(item.get("capabilities")))}
            if self.cache_path is not None:
                try:
                    await asyncio.to_thread(ProviderStore.write, self.cache_path,
                                            {"account": self.account, "devices": devices}, 4 * 1024 * 1024)
                except (OSError, ValueError):
                    raise CloudError("cloud_failed", 502) from None
            self.device_cache = devices
            self.scene_cache = {key: row for key, row in self.scene_cache.items() if key[0] in devices}
            return devices

    async def device(self, identifier):
        if not isinstance(identifier, str):
            raise ValueError("Invalid device")
        device = self.device_cache.get(identifier)
        if device is None:
            raise CloudError("unknown_device", 404)
        return device

    async def scenes(self, device):
        cache_key = (device["id"], device["sku"])
        async with self.lock:
            cached = self.scene_cache.get(cache_key)
            if cached and monotonic() < cached[0]:
                return cached[1]
            scenes = scene_options(device["caps"])
            supports_dynamic = any(cap.get("type") == "devices.capabilities.dynamic_scene"
                                   and cap.get("instance") == "lightScene" for cap in device["caps"])
            if supports_dynamic:
                result = await self.request("POST", "/device/scenes",
                                            {"device": device["id"], "sku": device["sku"]})
                payload = result.get("payload")
                if not isinstance(payload, dict):
                    raise CloudError("cloud_failed", 502)
                scenes.update(scene_options(objects(payload.get("capabilities"))))
            self.scene_cache[cache_key] = (monotonic() + 300, scenes)
            return scenes

    async def details(self, device):
        segments = {action: spec for action in SEGMENT_ACTIONS
                    if (spec := segment_spec(device["caps"], action))}
        scene_error = None
        try:
            scenes = await self.scenes(device)
        except CloudError as error:
            scenes = scene_options(device["caps"])
            scene_error = error.code
        return {"segments": segments, "scenes": [{"id": key, "name": row[0]} for key, row in scenes.items()],
                "scene_error": scene_error}

    async def capability(self, device, body):
        action = body["action"]
        if action == "scene":
            scene = body["scene"]
            if not isinstance(scene, str):
                raise ValueError("Invalid scene")
            selected = scene_options(device["caps"]).get(scene)
            if selected is None:
                selected = (await self.scenes(device)).get(scene)
            if selected is None:
                raise ValueError("Unknown scene")
            return selected[1]
        spec = segment_spec(device["caps"], action) if isinstance(action, str) and action in SEGMENT_ACTIONS else None
        indices = body.get("segments")
        if (not spec or not isinstance(indices, list) or not spec["minimum"] <= len(indices) <= spec["limit"]
                or any(type(index) is not int or index not in spec["indices"] for index in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError("Invalid segment selection")
        instance, name = SEGMENT_ACTIONS[action]
        if action == "color":
            red, green, blue = rgb(body["value"])
            value = red << 16 | green << 8 | blue
        else:
            value = body["value"]
            if (type(value) is not int or not spec["low"] <= value <= spec["high"]
                    or (value - spec["low"]) % spec["step"]):
                raise ValueError("Invalid segment brightness")
        return {"type": SEGMENT_TYPE, "instance": instance, "value": {"segment": indices, name: value}}

    async def apply(self, device, capability):
        await self.commands.run(lambda: self.request(
            "POST", "/device/control", {"device": device["id"], "sku": device["sku"], "capability": capability}
        ))


def install(app, key, control_context, cache_path=None):
    cloud = GoveeCloud(key, cache_path)

    def response(value, status=200):
        return web.json_response(value, status=status, headers=HEADERS)

    def public_devices(devices):
        return [{key: row[key] for key in ("id", "sku", "name")} for row in devices.values()]

    async def status(request):
        return response({"configured": bool(cloud.key), "devices": public_devices(cloud.device_cache)})

    async def manage(request):
        try:
            operation = request.match_info["operation"]
            if operation == "devices":
                devices = await cloud.devices()
                return response({"devices": public_devices(devices)})
            body = await request.json()
            device = await cloud.device(body["device"])
            if operation == "details":
                return response(await cloud.details(device))
            capability = await cloud.capability(device, body)
            async with control_context(device["id"]):
                await cloud.apply(device, capability)
            return response({"accepted": True})
        except CloudError as error:
            return response({"error": error.code}, error.status)
        except (ValueError, KeyError, TypeError, RecursionError):
            return response({"error": "invalid_cloud_request"}, 400)

    app.router.add_get("/providers/govee/cloud", status)
    app.router.add_post("/providers/govee/cloud/{operation:devices|details|apply}", manage)
