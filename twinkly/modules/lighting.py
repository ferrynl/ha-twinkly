"""Common lighting inventory and controls for ingress clients."""
import asyncio
import json
import time
import uuid

from aiohttp import ClientError, web

from .common import brightness, rgb
from .profiles import color_from_xy, govee_profile
from .mixed_music import MixedMusic

ERRORS = (ClientError, OSError, RuntimeError, TimeoutError, ValueError, web.HTTPException)
CAPABILITY = {"power": "power", "brightness": "brightness", "color": "rgb", "temperature": "temperature"}
MAX_MEMBERS = 128
MAX_GROUPS = 40
MAX_SCENES = 40
PROVIDERS = ("twinkly", "hue", "govee")
COMMAND_SNAPSHOT_SECONDS = 45


def light_key(*parts):
    return json.dumps(parts, separators=(",", ":"))


def selected_provider(body):
    provider = body.get("provider", "all")
    if provider not in (*PROVIDERS, "all"):
        raise ValueError("Invalid lighting provider")
    return provider


def provider_members(members, provider):
    if provider == "all":
        return members
    prefix = json.dumps([provider])[:-1] + ","
    return [member for member in members if member.startswith(prefix)]


def scene_settings(body):
    name, group, on = body["name"], body["group"], body["on"]
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
            or not isinstance(group, str) or type(on) is not bool):
        raise ValueError("Invalid scene")
    scene = {"name": name.strip(), "group": group, "on": on}
    if on and body.get("brightness") is not None:
        scene["brightness"] = brightness(body["brightness"])
    if on and body.get("color") is not None:
        scene["color"] = rgb(body["color"])
        if not any(scene["color"]):
            raise ValueError("Use power off for black")
    return scene


class Lighting:
    def __init__(self, controller, store, provider_inventory, provider_control):
        self.controller = controller
        self.store = store
        self.provider_inventory = provider_inventory
        self.provider_control = provider_control
        self.group_lock = asyncio.Lock()
        self.control_lock = asyncio.Lock()
        self.music = MixedMusic(controller, self.send)
        self.lamp_test = None
        self.command_snapshot = None

    async def lights(self, providers=PROVIDERS[1:]):
        lights = {}
        for identifier, device in self.controller.devices.items():
            key = light_key("twinkly", identifier)
            lights[key] = {
                "id": key, "provider": "twinkly", "name": device.row["name"],
                "product_code": getattr(device, "product_code", None),
                "status": "unavailable" if device.offline else ("unknown" if device.mode is None else "online"),
                "capabilities": {"power": True, "brightness": True, "rgb": True},
                "state": {"on": None if device.mode is None or device.offline else device.mode != "off",
                          "brightness": device.last_brightness,
                          "color": device.last_color if device.mode == "color" else None},
            }

        inventories = await asyncio.gather(*(self.provider_inventory(brand) for brand in providers),
                                           return_exceptions=True)
        connections = {}
        for brand, records in zip(providers, inventories):
            if isinstance(records, ERRORS):
                connections[brand] = None
                continue
            if isinstance(records, BaseException):
                raise records
            connections[brand] = [{field: row[field] for field in ("id", "address", "status")} for row in records]
            for row in records:
                if brand == "govee":
                    profile = govee_profile({"device": row["id"], "sku": row.get("sku")}, row.get("report"))
                    profiles = [profile]
                else:
                    profiles = row["lights"]
                for profile in profiles:
                    key = light_key(brand, row["id"], profile["id"])
                    state = dict(profile["state"])
                    if brand == "hue":
                        state["color"] = color_from_xy(state.pop("xy", None))
                    status = profile.get("status", row["status"]) if row["status"] == "online" else row["status"]
                    lights[key] = {**profile, "provider": brand, "state": state, "id": key, "status": status}
        return lights, connections

    def spatial_groups(self, groups=None):
        if groups is None:
            groups = self.store.load_groups()
        targets = {}
        display_groups = getattr(self.controller, "display_groups", lambda: {})()
        ordered = sorted(display_groups.items(), key=lambda item: not (
            item[0].startswith("native:") or item[1].get("native")
        ))
        memberships = set()
        for key, group in ordered:
            members = [light_key("twinkly", member) for member in group["members"]]
            if members:
                targets[light_key("group", "twinkly:" + key)] = {
                    "name": group["name"], "members": members, "provider": "twinkly",
                }
                memberships.add(frozenset(members))
        for key, group in (groups or {}).items():
            members = group["members"]
            if members and frozenset(members) not in memberships:
                targets[light_key("group", key)] = {"name": group["name"], "members": members}
        return targets

    async def inventory(self, request):
        lights, connections = await self.lights()
        self.command_snapshot = (time.monotonic(), lights, connections)
        try:
            groups = self.store.load_groups()
        except ERRORS:
            groups = None
        try:
            scenes = self.store.load_scenes()
        except ERRORS:
            scenes = None
        return web.json_response({"lights": list(lights.values()), "connections": connections,
                                  "groups": groups, "scenes": scenes, "spatial_groups": self.spatial_groups(groups or {}),
                                  "music": self.music.status()})

    async def command_lights(self, members, provider):
        if members is None:
            providers = tuple(brand for brand in PROVIDERS[1:] if provider in ("all", brand))
            requested = set()
        else:
            by_provider = {brand: provider_members(members, brand) for brand in PROVIDERS[1:]}
            providers = tuple(brand for brand, keys in by_provider.items() if keys)
            requested = {key for keys in by_provider.values() for key in keys}
        if self.command_snapshot and providers:
            created, lights, connections = self.command_snapshot
            if (time.monotonic() - created < COMMAND_SNAPSHOT_SECONDS
                    and all(connections.get(brand) is not None for brand in providers)
                    and requested.issubset(lights)):
                twinkly, _ = await self.lights(())
                return {**{key: light for key, light in lights.items() if light["provider"] in providers}, **twinkly}
        lights, _ = await self.lights(providers)
        return lights

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
                elif identifier and "member" in body:
                    member = body["member"]
                    known, _ = await self.lights()
                    if not isinstance(member, str) or member not in known:
                        raise ValueError("Unknown lamp")
                    members = list(dict.fromkeys([*groups[identifier]["members"], member]))
                    if len(members) > MAX_MEMBERS:
                        raise ValueError("Too many members")
                    groups[identifier]["members"] = members
                else:
                    name, members = body.get("name"), body.get("members")
                    kind = body.get("kind", groups.get(identifier, {}).get("kind", "group"))
                    if kind not in ("group", "room"):
                        raise ValueError("Invalid group type")
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
                    if kind == "room":
                        groups[identifier]["kind"] = kind
                self.store.save_groups(groups)
            async with self.control_lock:
                if self.music.group == identifier:
                    await self.music.stop()
            return web.json_response({"id": identifier})
        except (ValueError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()

    async def save_scene(self, request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError()
            identifier = body.get("id")
            async with self.group_lock:
                scenes = self.store.load_scenes()
                if identifier is not None and (not isinstance(identifier, str) or identifier not in scenes):
                    raise web.HTTPNotFound()
                if body.get("delete") is True:
                    if identifier is None:
                        raise ValueError()
                    del scenes[identifier]
                else:
                    scene = scene_settings(body)
                    if scene["group"] not in self.store.load_groups() or (identifier is None and len(scenes) >= MAX_SCENES):
                        raise ValueError()
                    identifier = identifier or uuid.uuid4().hex
                    scenes[identifier] = scene
                self.store.save_scenes(scenes)
            return web.json_response({"id": identifier})
        except (ValueError, KeyError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()

    def valid_show(self, show):
        group = show["group"]
        scenes = self.store.load_scenes()
        groups = self.store.load_groups()
        return all(
            step.get("group", group) in groups
            and scenes.get(step["scene"], {}).get("group") == step.get("group", group)
            for step in show["steps"]
        )

    async def run_scene(self, identifier, expected_group=None, provider="all"):
        async with self.control_lock:
            scene = self.store.load_scenes().get(identifier)
            if scene is None:
                raise web.HTTPNotFound()
            scene = scene_settings(scene)
            if expected_group is not None and scene["group"] != expected_group:
                raise web.HTTPConflict()
            group = self.store.load_groups().get(scene["group"])
            if group is None:
                raise web.HTTPConflict()
            members = provider_members(group["members"], provider)
            if self.lamp_test and self.lamp_test.target in members:
                await self.lamp_test.stop()
            if self.music.members.intersection(members):
                await self.music.stop()
            lights = await self.command_lights(members, provider)
            commands = [("power", scene["on"])]
            commands.extend((action, scene[action]) for action in ("color", "brightness") if action in scene)
            results = {key: {} for key in members}
            for action, value in commands:
                outcomes = await asyncio.gather(*(self.send(key, lights.get(key), action, value) for key in members))
                for key, outcome in zip(members, outcomes):
                    results[key][action] = outcome
            return results

    async def apply_scene(self, request):
        try:
            body = await request.json() if request.can_read_body else {}
            if not isinstance(body, dict):
                raise ValueError()
            provider = selected_provider(body)
        except (ValueError, TypeError):
            raise web.HTTPBadRequest()
        try:
            return web.json_response({"results": await self.run_scene(request.match_info["id"], provider=provider)})
        except (ValueError, KeyError, TypeError, OSError):
            raise web.HTTPServiceUnavailable()

    async def control_music(self, request):
        try:
            body = await request.json()
            if not isinstance(body, dict):
                raise ValueError()
            async with self.control_lock:
                if body.get("stop") is True:
                    report = await self.music.stop()
                    result = self.music.status()
                    if report:
                        result["restoration"] = report
                    return web.json_response(result)
                group = body["group"]
                if "level" in body:
                    level = body["level"]
                    if type(level) is not int or not 1 <= level <= 100:
                        raise ValueError()
                    if self.music.group != group or self.music.task is None:
                        raise web.HTTPConflict()
                    results = await self.music.set_level(level)
                    return web.json_response({**self.music.status(), "results": results})
                members = self.store.load_groups()[group]["members"]
                if self.lamp_test and self.lamp_test.target in members:
                    await self.lamp_test.stop()
                await self.music.stop()
                lights, _ = await self.lights()
                result = await self.music.start(group, {key: lights.get(key) for key in members})
                return web.json_response({**self.music.status(), **result})
        except (ValueError, KeyError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()

    async def music_cleanup(self, app):
        yield
        async with self.control_lock:
            if self.lamp_test:
                await self.lamp_test.stop()
            await self.music.stop()

    async def send_spatial_color(self, key, light, color, stop):
        async with self.control_lock:
            if stop.is_set() or key in self.music.members or (self.lamp_test and self.lamp_test.target == key):
                return "skipped"
            return await self.send(key, light, "color", color)

    async def send_spatial_group_color(self, lights, color, stop):
        async with self.control_lock:
            if stop.is_set():
                return {}
            async def apply(key, light):
                if key in self.music.members or (self.lamp_test and self.lamp_test.target == key):
                    return "skipped"
                return await self.send(key, light, "color", color)
            outcomes = await asyncio.gather(*(apply(key, light) for key, light in lights.items()))
            return dict(zip(lights, outcomes))

    async def send(self, key, light, action, value):
        if (not light or not light["capabilities"].get(CAPABILITY[action])
                or light["status"] == "unavailable"):
            return "skipped"
        brand, *parts = json.loads(key)
        if action == "temperature":
            limits = light.get("temperature_mirek")
            valid = ((brand == "hue" and limits and limits["min"] <= value <= limits["max"])
                     or (brand == "govee" and 2000 <= value <= 9000))
            if not valid:
                return "skipped"
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
            provider = selected_provider(body)
            if action == "power" and type(value) is bool:
                pass
            elif action == "brightness":
                value = brightness(value)
            elif action == "color":
                value = rgb(value)
                if not any(value):
                    raise ValueError()
            elif (action == "temperature" and type(value) is int and isinstance(body.get("id"), str) and "group" not in body
                  and (1 <= value <= 1000 or 2000 <= value <= 9000)):
                pass
            else:
                raise ValueError()
            if "group" in body:
                members = self.store.load_groups()[body["group"]]["members"]
            elif isinstance(body.get("id"), str):
                members = [body["id"]]
            elif "provider" in body:
                members = None
            else:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise web.HTTPBadRequest()
        except OSError:
            raise web.HTTPServiceUnavailable()
        async with self.control_lock:
            lights = None
            if members is None:
                lights = await self.command_lights(members, provider)
                members = list(lights)
            members = provider_members(members, provider)
            if self.lamp_test and self.lamp_test.target in members:
                await self.lamp_test.stop()
            if self.music.members.intersection(members):
                await self.music.stop()
            if lights is None:
                lights = await self.command_lights(members, provider)
            results = await asyncio.gather(*(self.send(key, lights.get(key), action, value) for key in members))
        return web.json_response({"results": dict(zip(members, results))})

    def install(self, router):
        router.add_get("/lighting", self.inventory)
        router.add_post("/lighting/groups", self.save_group)
        router.add_post("/lighting/control", self.control)
        router.add_post("/lighting/music", self.control_music)
        router.add_post("/lighting/scenes", self.save_scene)
        router.add_post("/lighting/scenes/{id}/apply", self.apply_scene)
