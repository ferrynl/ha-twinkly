"""Common lighting inventory and controls for ingress clients."""
import asyncio
import json
import math
import uuid

from aiohttp import ClientError, web

from .common import brightness, rgb
from .profiles import govee_profile

ERRORS = (ClientError, OSError, RuntimeError, TimeoutError, ValueError, web.HTTPException)
CAPABILITY = {"power": "power", "brightness": "brightness", "color": "rgb"}
MAX_MEMBERS = 128
MAX_GROUPS = 40


def light_key(*parts):
    return json.dumps(parts, separators=(",", ":"))


def color_from_xy(xy):
    if not isinstance(xy, dict):
        return None
    x, y = xy.get("x"), xy.get("y")
    if not all(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1 for v in (x, y)) or y < .001:
        return None
    X, Z = x / y, (1 - x - y) / y
    linear = (1.656492 * X - .354851 - .255038 * Z,
              -.707196 * X + 1.655397 + .036152 * Z,
              .051713 * X - .121364 + 1.011530 * Z)
    scale = max(1, *linear)
    channels = [max(0, value / scale) for value in linear]
    return [round(255 * (12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055))
            for c in channels]


class Lighting:
    def __init__(self, controller, store, provider_inventory, provider_control):
        self.controller = controller
        self.store = store
        self.provider_inventory = provider_inventory
        self.provider_control = provider_control
        self.group_lock = asyncio.Lock()

    async def lights(self):
        lights = {}
        for identifier, device in self.controller.devices.items():
            key = light_key("twinkly", identifier)
            lights[key] = {
                "id": key, "provider": "twinkly", "name": device.row["name"],
                "status": "unavailable" if device.offline else ("unknown" if device.mode is None else "online"),
                "capabilities": {"power": True, "brightness": True, "rgb": True},
                "state": {"on": None if device.mode is None or device.offline else device.mode != "off",
                          "brightness": device.last_brightness,
                          "color": device.last_color if device.mode == "color" else None},
            }

        inventories = await asyncio.gather(*(self.provider_inventory(brand) for brand in ("hue", "govee")),
                                           return_exceptions=True)
        connections = {}
        for brand, records in zip(("hue", "govee"), inventories):
            if isinstance(records, ERRORS):
                connections[brand] = None
                continue
            if isinstance(records, BaseException):
                raise records
            connections[brand] = [{field: row[field] for field in ("id", "address", "status")} for row in records]
            for row in records:
                if brand == "govee":
                    profile = govee_profile({"device": row["id"], "sku": row["id"]}, row.get("report"))
                    profiles = [profile]
                else:
                    profiles = row["lights"]
                for profile in profiles:
                    key = light_key(brand, row["id"], profile["id"])
                    state = dict(profile["state"])
                    if brand == "hue":
                        state["color"] = color_from_xy(state.pop("xy", None))
                    lights[key] = {**profile, "state": state, "id": key, "status": row["status"]}
        return lights, connections

    async def inventory(self, request):
        lights, connections = await self.lights()
        try:
            groups = self.store.load_groups()
        except ERRORS:
            groups = None
        return web.json_response({"lights": list(lights.values()), "connections": connections, "groups": groups})

    async def save_group(self, request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError()
            identifier = body.get("id")
            async with self.group_lock:
                groups = self.store.load_groups()
                if identifier is not None and (not isinstance(identifier, str) or identifier not in groups):
                    raise web.HTTPNotFound()
                if body.get("delete") is True and identifier:
                    del groups[identifier]
                else:
                    name, members = body.get("name"), body.get("members")
                    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
                            or not isinstance(members, list) or not 1 <= len(members) <= MAX_MEMBERS
                            or any(not isinstance(member, str) or len(member) > 512 for member in members)
                            or (identifier is None and len(groups) >= MAX_GROUPS)):
                        raise ValueError()
                    known, _ = await self.lights()
                    previous = groups[identifier]["members"] if identifier else []
                    if any(member not in known and member not in previous for member in members):
                        raise ValueError()
                    identifier = identifier or uuid.uuid4().hex
                    groups[identifier] = {"name": name.strip(), "members": list(dict.fromkeys(members))}
                self.store.save_groups(groups)
            return web.json_response({"id": identifier})
        except (ValueError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()

    async def send(self, key, light, action, value):
        if (not light or not light["capabilities"].get(CAPABILITY[action])
                or light["status"] == "unavailable"):
            return "skipped"
        brand, *parts = json.loads(key)
        try:
            if brand == "twinkly":
                payload = {"id": parts[0], "action": action, "value": value}
                if action == "power":
                    payload["action"] = "on" if value else "off"
                elif action == "color":
                    payload["value"] = "#" + bytes(value).hex()
                result = await self.controller.apply_control(payload)
                return "failed" if result["failed"] or result.get("offline") else "accepted"
            identifier, light_id = parts
            await self.provider_control(brand, identifier, light_id, action, value)
            return "unconfirmed" if brand == "govee" else "accepted"
        except (*ERRORS, KeyError):
            return "failed"

    async def control(self, request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError()
            action, value = body["action"], body["value"]
            if action == "power" and type(value) is bool:
                pass
            elif action == "brightness":
                value = brightness(value)
            elif action == "color":
                value = rgb(value)
                if not any(value):
                    raise ValueError()
            else:
                raise ValueError()
            if "group" in body:
                members = self.store.load_groups()[body["group"]]["members"]
            elif isinstance(body.get("id"), str):
                members = [body["id"]]
            else:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()
        lights, _ = await self.lights()
        results = await asyncio.gather(*(self.send(key, lights.get(key), action, value) for key in members))
        return web.json_response({"results": dict(zip(members, results))})

    def install(self, router):
        router.add_get("/lighting", self.inventory)
        router.add_post("/lighting/groups", self.save_group)
        router.add_post("/lighting/control", self.control)
