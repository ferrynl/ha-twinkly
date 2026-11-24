"""Shared lighting projects and mixed-show playback behind Home Assistant Ingress."""
import asyncio
import base64
from hashlib import sha256
from io import BytesIO
import json
import logging
import math
import os
import re
import uuid

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web
from PIL import Image, ImageOps, UnidentifiedImageError

from .common import rgb
from .lighting import ERRORS

LOG = logging.getLogger(__name__)
MAX_PHOTO = 470_000
MAX_SHOWS = 20
MAX_STEPS = 20
MAX_WALLS = 24
PLAN_SLOTS = 8 * 4
PROJECT_LIMIT = 18 * 1024 * 1024
DEFAULT_WALL = "default"
RADIAL_EFFECTS = {"outward": 1, "inward": -1}
DIRECTIONS = {"right": (0, 1), "left": (0, -1), "down": (1, 1), "up": (1, -1)}
HEADERS = {
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


def empty_layout():
    return {"revision": None, "photo_version": None, "photo": None, "points": []}


def photo_jpeg(value):
    if not isinstance(value, str) or len(value) > 4 * ((MAX_PHOTO + 2) // 3):
        raise ValueError("Invalid photo size")
    raw = base64.b64decode(value, validate=True)
    if not 4 <= len(raw) <= MAX_PHOTO:
        raise ValueError("Invalid photo size")
    with Image.open(BytesIO(raw), formats=["JPEG", "PNG", "WEBP"]) as image:
        if not 1 <= min(image.size) <= max(image.size) <= 2048:
            raise ValueError("Invalid photo dimensions")
        # Re-encode pixels without retaining the source's metadata.
        pixels = ImageOps.exif_transpose(image).convert("RGB")
        pixels.thumbnail((1280, 1280))
        clean = Image.new("RGB", pixels.size)
        clean.paste(pixels)
        out = BytesIO()
        clean.save(out, "JPEG", quality=80, optimize=True)
        if out.tell() > MAX_PHOTO:
            raise ValueError("Photo too large")
        return base64.b64encode(out.getvalue()).decode("ascii")


def positions(value):
    if not isinstance(value, list) or len(value) > 128:
        raise ValueError("Invalid positions")
    points = {}
    for key, coordinate in value:
        parts = json.loads(key)
        if (not isinstance(parts, list) or not parts or parts[0] not in ("twinkly", "hue", "govee", "group")
                or len(parts) != (2 if parts[0] in ("twinkly", "group") else 3)
                or any(not isinstance(part, str) or not 1 <= len(part) <= 128 for part in parts)):
            raise ValueError("Invalid light")
        if (not isinstance(coordinate, list) or len(coordinate) not in (2, 3, 4, 5, 6)
                or any(type(n) not in (int, float) or not 0 <= n <= 100 for n in coordinate[:2])
                or (len(coordinate) >= 3 and (type(coordinate[2]) not in (int, float)
                                             or not 4 <= coordinate[2] <= 40))
                or (len(coordinate) >= 4 and (type(coordinate[3]) is not int or not 0 <= coordinate[3] <= 1000))
                or (len(coordinate) >= 5 and (type(coordinate[4]) is not int or not -180 <= coordinate[4] <= 180))
                or (len(coordinate) == 6 and (type(coordinate[5]) not in (int, float)
                                             or not 4 <= coordinate[5] <= 100))):
            raise ValueError("Invalid position")
        points[json.dumps(parts, separators=(",", ":"))] = coordinate
    return list(points.items())


def identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise ValueError("Invalid identifier")
    return value


def show_settings(data):
    name, group, steps = data["name"], identifier(data["group"]), data["steps"]
    if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
            or not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS):
        raise ValueError("Invalid show")
    normalized = []
    for step in steps:
        seconds = step["seconds"]
        if type(seconds) is not int or not 1 <= seconds <= 300:
            raise ValueError("Invalid hold time")
        cue = {"scene": identifier(step["scene"]), "seconds": seconds}
        if "group" in step:
            cue["group"] = identifier(step["group"])
        normalized.append(cue)
    show = {"name": name.strip(), "group": group, "steps": normalized}
    if data.get("music") is not None:
        show["music"] = music_settings(data["music"])
    return show


def music_settings(music):
    player, media_id = music["player"], music["media_id"]
    media_type = music.get("media_type", "")
    if (not isinstance(player, str) or len(player) > 255
            or not re.fullmatch(r"media_player\.[a-z0-9_]+", player)
            or not isinstance(media_id, str) or not 1 <= len(media_id.strip()) <= 500
            or media_type not in ("", "track", "playlist", "album", "radio")):
        raise ValueError("Invalid show music")
    return {"player": player, "media_id": media_id.strip(), "media_type": media_type}


def spatial_position(point, direction, effect):
    radial = RADIAL_EFFECTS.get(effect)
    if radial is not None:
        return radial * ((point[0] - 50) ** 2 + (point[1] - 50) ** 2)
    axis, sign = DIRECTIONS[direction]
    return sign * point[axis]


def spatial_steps(eligible, lights, axis, sign, color, delay, end_color):
    if not eligible:
        return []
    first = sign * eligible[0][1][axis]
    distance = sign * eligible[-1][1][axis] - first
    advances = [point[3] if len(point) >= 4 else 0 for _, point in eligible]
    calibrated = any(advances) or end_color is not None
    steps = []
    for index, ((key, point), advance) in enumerate(zip(eligible, advances)):
        channels = color
        if end_color is not None and distance:
            ratio = (sign * point[axis] - first) / distance
            channels = [int(start + (end - start) * ratio + 0.5) for start, end in zip(color, end_color)]
            if not any(channels):
                channels[channels.index(max(channels))] = 1
        step = {"lamp": key, "light": lights[key], "color": channels, "seconds": delay / 1000}
        if calibrated:
            step["due"] = (0 if end_color is not None else index * delay) - advance
        steps.append(step)
    if calibrated:
        steps.sort(key=lambda step: step["due"])
        earliest = steps[0]["due"]
        for step in steps:
            step["due"] = (step["due"] - earliest) / 1000
    return steps


CORE_API = "http://supervisor/core/api"
MUSIC_PLAYERS_TEMPLATE = """
{%- set ns = namespace(players=[]) -%}
{%- for entity in expand(integration_entities('music_assistant')) -%}
  {%- if entity.domain == 'media_player' and entity.attributes.get('device_class') != 'tv' -%}
    {%- set ns.players = ns.players + [{'id': entity.entity_id, 'name': entity.name, 'state': entity.state}] -%}
  {%- endif -%}
{%- endfor -%}
{{ ns.players | to_json }}
"""


async def core_music_request(path, data):
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise ValueError("Home Assistant API is unavailable")
    async with ClientSession(timeout=ClientTimeout(total=8)) as session:
        async with session.post(
            f"{CORE_API}/{path}",
            headers={"Authorization": f"Bearer {token}"}, json=data, allow_redirects=False,
        ) as response:
            response.raise_for_status()
            return await response.text()


async def music_assistant_players():
    return json.loads(await core_music_request("template", {"template": MUSIC_PLAYERS_TEMPLATE}))


async def show_music_service(service, data):
    await core_music_request(f"services/{service}", data)


async def start_show_music(music):
    players = await music_assistant_players()
    if not any(player["id"] == music["player"] and player["state"] not in ("unknown", "unavailable")
               for player in players):
        raise ValueError("Selected Music Assistant player is unavailable")
    payload = {"entity_id": music["player"], "media_id": music["media_id"], "enqueue": "play"}
    if music.get("media_type"):
        payload["media_type"] = music["media_type"]
    await show_music_service("music_assistant/play_media", payload)


class Playback:
    def __init__(self, lighting):
        self.lighting = lighting
        self.task = None
        self.stop = asyncio.Event()
        self.status = {"state": "idle"}

    def start(self, show):
        if not self.lighting.valid_show(show):
            raise ValueError("Unavailable scene")

        async def apply(step):
            return await self.lighting.run_scene(step["scene"], step.get("group", show["group"]))

        self.schedule("show", show["steps"], apply, show["id"], music=show.get("music"))

    def preview_music(self, music):
        async def apply(_step):
            return {"music": {"play": "accepted"}}

        self.schedule("music", [{"seconds": 12}], apply, music=music)

    def start_spatial(self, points, direction, color, delay, end_color=None, effect=None):
        axis, sign = DIRECTIONS[direction]
        async def plan():
            lights, _ = await self.lighting.lights()
            groups = getattr(self.lighting, "spatial_groups", lambda: {})()
            owners = {}
            for group, row in groups.items():
                for member in row["members"]:
                    owners.setdefault(member, group)
            placements = dict(points)
            for key, point in points:
                group = owners.get(key)
                if group is not None:
                    placements.setdefault(group, point)
                    placements.pop(key, None)

            eligible = []
            targets = {}
            claimed = set()
            for key, point in sorted(placements.items(), key=lambda item: spatial_position(item[1], direction, effect)):
                members = groups.get(key, {}).get("members", [key])
                active = {}
                for member in members:
                    light = lights.get(member)
                    if (member not in claimed and light and light["status"] != "unavailable"
                            and light["capabilities"].get("rgb") and light["state"].get("on") is True):
                        active[member] = light
                if active:
                    claimed.update(active)
                    eligible.append((key, point))
                    targets[key] = active if key in groups else active[key]
            return spatial_steps(eligible, targets, axis, sign, color, delay, end_color)

        async def apply(step):
            key = step["lamp"]
            if json.loads(key)[0] == "group":
                return {key: await self.lighting.send_spatial_group_color(step["light"], step["color"], self.stop)}
            result = await self.lighting.send_spatial_color(key, step["light"], step["color"], self.stop)
            return {key: {"color": result}}

        self.schedule("spatial", [], apply, prepare=plan)
        self.status["effect"] = effect or ("gradient" if end_color is not None else "sweep")

    def schedule(self, kind, steps, apply, identifier=None, prepare=None, music=None):
        if self.task is not None:
            raise web.HTTPConflict()
        self.stop.clear()
        self.status = {"state": "playing", "kind": kind, "id": identifier, "step": 0, "total": len(steps),
                       "uncertain": False, "partial": False, "last": None}
        self.task = asyncio.create_task(self.run(steps, apply, prepare, music))

    async def run(self, steps, apply, prepare, music=None):
        outcome = "complete"
        music_started = False
        try:
            if music and not self.stop.is_set():
                try:
                    await start_show_music(music)
                    music_started = True
                except (ClientError, TimeoutError, ValueError):
                    LOG.warning("Music Assistant could not start show music", exc_info=True)
                    self.status["music_error"] = "start"
                    if self.status["kind"] == "music":
                        outcome = "failed"
                        return
            if prepare:
                steps = await prepare()
                self.status["total"] = len(steps)
            succeeded = False
            loop = asyncio.get_running_loop()
            timeline_start = loop.time()
            due = timeline_start
            for number, step in enumerate(steps, 1):
                if "due" in step:
                    due = timeline_start + step["due"]
                    await self.wait_until_stopped(due - loop.time())
                if self.stop.is_set():
                    break
                self.status["step"] = number
                started = loop.time()
                results = await apply(step)
                self.status["last"] = {"step": number, "milliseconds": round((loop.time() - started) * 1000),
                                       "results": results}
                if self.status["kind"] == "spatial":
                    self.status.setdefault("timing", []).append({
                        "lamp": step["lamp"],
                        "planned_ms": round((due - timeline_start) * 1000),
                        "sent_ms": round((started - timeline_start) * 1000),
                        "command_ms": self.status["last"]["milliseconds"],
                    })
                outcomes = {value for commands in results.values() for value in commands.values()}
                self.status["uncertain"] |= "unconfirmed" in outcomes
                self.status["partial"] |= bool(outcomes.intersection({"failed", "skipped"}))
                sent = bool(outcomes.intersection({"accepted", "unconfirmed"}))
                succeeded |= sent
                if not sent and prepare is None:
                    outcome = "failed"
                    break
                if prepare and number == len(steps):
                    break
                if "due" not in step:
                    due = loop.time() + step["seconds"]
                    await self.wait_until_stopped(step["seconds"])
            if not succeeded:
                outcome = "failed"
        except (*ERRORS, KeyError, TypeError):
            LOG.exception("Lighting playback interrupted")
            outcome = "failed"
        finally:
            if music_started:
                try:
                    await show_music_service("media_player/media_stop", {"entity_id": music["player"]})
                except (ClientError, TimeoutError, ValueError):
                    LOG.warning("Music Assistant could not stop show music", exc_info=True)
                    self.status["music_error"] = "stop"
            self.status["state"] = "stopped" if self.stop.is_set() else outcome
            self.task = None

    async def wait_until_stopped(self, seconds):
        if seconds > 0:
            try:
                await asyncio.wait_for(self.stop.wait(), seconds)
            except TimeoutError:
                pass

    def request_stop(self):
        if self.task is not None:
            self.stop.set()
            self.status["state"] = "stopping"

    async def cleanup(self, app):
        yield
        self.request_stop()
        if self.task is not None:
            await self.task


def wall_layout(data, wall_id):
    return data["layout"] if wall_id == DEFAULT_WALL else data["walls"][wall_id]


def wall_dimensions(body):
    width, height = body["width_m"], body["height_m"]
    if any(type(value) not in (int, float) or not 0.25 <= value <= 20 for value in (width, height)):
        raise ValueError("Invalid wall dimensions")
    return {"width_m": round(width, 2), "height_m": round(height, 2)}


def wall_name(data):
    name = data["name"]
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
        raise ValueError("Invalid wall name")
    return name.strip()


def update_wall_layout(data, wall_id, layout):
    if wall_id == DEFAULT_WALL:
        data["layout"] = layout
    else:
        data["walls"][wall_id] = {**data["walls"][wall_id], **layout}


def plan_slots(data):
    walls = (DEFAULT_WALL, *data["walls"])
    saved = data.get("plan_slots", {})
    assigned = {}
    for wall_id in walls:
        slot = saved.get(wall_id)
        if type(slot) is int and 0 <= slot < PLAN_SLOTS and slot not in assigned.values():
            assigned[wall_id] = slot
    free = iter(sorted(set(range(PLAN_SLOTS)) - set(assigned.values())))
    for wall_id in walls:
        if wall_id not in assigned:
            assigned[wall_id] = next(free)
    return assigned


def wall_placement(value):
    x, z, angle = (value[key] for key in ("x_m", "z_m", "angle"))
    if (any(type(n) not in (int, float) or not -20 <= n <= 20 for n in (x, z))
            or type(angle) is not int or not -180 <= angle <= 180):
        raise ValueError("Invalid wall placement")
    return {"x_m": round(x, 2), "z_m": round(z, 2), "angle": angle}


def tree_placement(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid tree")
    height = value["height_m"]
    if type(height) not in (int, float) or not 0.5 <= height <= 5:
        raise ValueError("Invalid tree height")
    return {**wall_placement(value), "height_m": round(height, 2)}


def plan_revision(data, slots):
    parts = [slots, data.get("wall_placements", {}), data.get("room_names", {}), data.get("trees", {}), data.get("room_groups", {}), data.get("room_positions", {}), data.get("ceiling_lights", {})]
    return sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()


def install(app, lighting):
    store = lighting.store
    path = store.path.parent / "lighting-projects.json"
    lock = asyncio.Lock()
    playback = Playback(lighting)
    invalid = (ValueError, KeyError, TypeError, OverflowError, UnidentifiedImageError, Image.DecompressionBombError)
    state = None

    async def load():
        nonlocal state
        if state is None:
            state = await asyncio.to_thread(
                store.read, path, {"shows": {}, "layout": empty_layout()}, PROJECT_LIMIT
            )
            state.setdefault("walls", {})
        return state

    async def start_voice_demo(event):
        room_name = event.get("room")
        if not isinstance(room_name, str) or not room_name.strip():
            raise ValueError("Specify a room name")
        groups = store.load_groups()
        matches = [(key, group) for key, group in groups.items()
                   if group.get("kind") == "room" and group["name"].casefold() == room_name.strip().casefold()]
        if len(matches) != 1:
            raise ValueError("Select a unique app room")
        room_id, room = matches[0]
        members = set(room["members"])
        data = await current()

        async def prepare():
            lights = await lighting.command_lights(room["members"], "all")
            grouped, claimed, targets = set(), set(), []
            spatial = lighting.spatial_groups(groups)
            for key, group in spatial.items():
                if group.get("provider") != "twinkly":
                    continue
                native = json.loads(key)[1].removeprefix("twinkly:")
                ids = set(group["members"])
                grouped.update(ids)
                if ids and ids <= members and not ids & claimed:
                    claimed.update(ids)
                    targets.append((key, native, group["members"]))
            targets.extend((key, None, [key]) for key in room["members"]
                           if key in lights and key not in grouped)

            def color_capable(target):
                return any(lights.get(key, {}).get("capabilities", {}).get("rgb")
                           and lights[key]["capabilities"].get("power")
                           and lights[key]["status"] != "unavailable" for key in target[2])

            coordinates = {}
            linked = next((int(slot) for slot, group in data.get("room_groups", {}).items() if group == room_id), None)
            for wall, slot in plan_slots(data).items():
                if linked is not None and slot // 4 != linked:
                    continue
                layout = wall_layout(data, wall)
                for key, point in layout["points"]:
                    side = slot % 4
                    offset = (point[0] / 100 - .5) * (layout.get("dimensions") or {}).get("width_m", 4)
                    placement = data.get("wall_placements", {}).get(wall)
                    x = ([offset, 3, -offset, -3][side] if placement is None else
                         placement["x_m"] + offset * math.cos(math.radians(placement["angle"])))
                    coordinates.setdefault(key, x)
                    for member in spatial.get(key, {}).get("members", []):
                        coordinates.setdefault(member, x)

            def position(target):
                key, _, ids = target
                return coordinates.get(key, min(coordinates.get(member, math.inf) for member in ids))

            colors = sorted(filter(color_capable, targets), key=position)
            if not colors:
                raise ValueError("Room has no available demo lights")
            palette = [(225,38,69), (24,170,91), (255,173,68), (100,68,238), (255,214,148)]
            steps = [{"commands": [(target, "power", False) for target in targets], "lights": lights, "seconds": .65}]
            for index, target in enumerate(colors + colors[::-1]):
                commands = [(target, "color", list(palette[index % len(palette)])), (target, "power", True)]
                steps.append({"commands": commands, "lights":lights, "seconds":1.2 if index < len(colors) else .75})
                steps.append({"commands":[(target, "power", False)], "lights":lights, "seconds":0})
            return steps

        async def apply(step):
            async with lighting.control_lock:
                results = {}
                for (key, native, ids), action, value in step["commands"]:
                    if playback.stop.is_set():
                        break
                    if any(member in lighting.music.members or
                           (lighting.lamp_test and lighting.lamp_test.target == member) for member in ids):
                        results[key] = {action: "skipped"}
                    elif native:
                        mode = action if action == "color" else ("on" if value else "off")
                        payload = {"group":native, "action":mode,
                                   "value":"#" + bytes(value).hex() if action == "color" else value}
                        reply = await lighting.controller.apply_control(payload)
                        results[key] = {action:"failed" if reply.get("failed") or reply.get("offline") else "accepted"}
                    else:
                        results[key] = {action:await lighting.send(key, step["lights"].get(key), action, value)}
                return results

        playback.schedule("demo", [], apply, identifier=room_id, prepare=prepare)

    async def voice_events(_app):
        token = os.environ.get("SUPERVISOR_TOKEN")
        if not token:
            yield
            return

        async def listen():
            async with ClientSession() as session:
                while True:
                    try:
                        async with session.ws_connect("ws://supervisor/core/websocket", heartbeat=30) as socket:
                            hello = await socket.receive_json(timeout=10)
                            if hello.get("type") != "auth_required":
                                raise ValueError("Unexpected Home Assistant handshake")
                            await socket.send_json({"type":"auth", "access_token":token})
                            if (await socket.receive_json(timeout=10)).get("type") != "auth_ok":
                                raise ValueError("Home Assistant authentication failed")
                            await socket.send_json({"id":1, "type":"subscribe_events",
                                                    "event_type":"christmas_control_center_demo"})
                            if not (await socket.receive_json(timeout=10)).get("success"):
                                raise ValueError("Home Assistant event subscription failed")
                            async for message in socket:
                                if message.type != WSMsgType.TEXT:
                                    continue
                                packet = message.json()
                                if packet.get("type") != "event":
                                    continue
                                event = packet["event"].get("data")
                                try:
                                    if isinstance(event, dict):
                                        if "show_id" in event:
                                            projects = await current()
                                            playback.start(projects["shows"][identifier(event["show_id"])])
                                        else:
                                            await start_voice_demo(event)
                                except web.HTTPConflict:
                                    LOG.info("Voice demo ignored because a show is already playing")
                                except (ValueError, OSError, KeyError):
                                    LOG.warning("Voice demo could not start. Check the room name and configuration.")
                    except (ClientError, TimeoutError, OSError, ValueError, KeyError, TypeError):
                        LOG.warning("Home Assistant voice demo connection unavailable; retrying")
                    await asyncio.sleep(10)

        listener = asyncio.create_task(listen())
        try:
            yield
        finally:
            listener.cancel()
            await asyncio.gather(listener, return_exceptions=True)

    async def current():
        if state is not None:
            return state
        async with lock:
            return await load()

    def response(data, wall_id, **extra):
        layout = wall_layout(data, wall_id)
        walls = [{"id": DEFAULT_WALL, "name": data["layout"].get("name", "")}]
        walls.extend({"id": key, "name": wall["name"]} for key, wall in data["walls"].items())
        return web.json_response({
            "shows": list(data["shows"].values()),
            "walls": walls, "wall_id": wall_id,
            "layout": {"revision": layout["revision"], "photo_version": layout["photo_version"],
                       "points": layout["points"], "dimensions": layout.get("dimensions")},
            "playback": playback.status, **extra,
        }, headers=HEADERS)

    async def get(request):
        try:
            data = await current()
            wall_id = request.query.get("wall", DEFAULT_WALL)
            if wall_id not in data["walls"]:
                wall_id = DEFAULT_WALL
            return response(data, wall_id)
        except (ValueError, OSError):
            raise web.HTTPServiceUnavailable()

    def overview_response(data):
        slots = plan_slots(data)
        placements = data.get("wall_placements", {})
        names = data.get("room_names", {})
        result = []
        for wall_id, slot in sorted(slots.items(), key=lambda item: item[1]):
            layout = wall_layout(data, wall_id)
            wall = {"id": wall_id, "name": layout.get("name", ""), "slot": slot,
                    "photo_version": layout["photo_version"], "points": layout["points"],
                    "revision": layout["revision"],
                    "dimensions": layout.get("dimensions")}
            if wall_id in placements:
                wall["placement"] = placements[wall_id]
            result.append(wall)
        return web.json_response({"revision": plan_revision(data, slots), "walls": result,
                                  "room_names": names, "ceiling_lights": data.get("ceiling_lights", {}), "room_positions": data.get("room_positions", {}), "room_groups": data.get("room_groups", {}), "trees": data.get("trees", {})}, headers=HEADERS)

    async def overview(request):
        try:
            return overview_response(await current())
        except (ValueError, OSError):
            raise web.HTTPServiceUnavailable()

    async def move_wall(request):
        nonlocal state
        try:
            body = await request.json()
            wall_id, slot, revision = body["wall"], body["slot"], body["revision"]
            if not isinstance(wall_id, str) or type(slot) is not int or not 0 <= slot < PLAN_SLOTS:
                raise ValueError("Invalid wall position")
            placement = wall_placement(body["placement"]) if body.get("placement") is not None else None
            if "room_name" in body:
                name = body["room_name"]
                if not isinstance(name, str) or len(name.strip()) > 60:
                    raise ValueError("Invalid room name")
                name = name.strip()
            group = body.get("room_group")
            if group is not None and (not isinstance(group, str) or not 1 <= len(group) <= 128):
                raise ValueError("Invalid room group")
            async with lock:
                latest = await load()
                slots = plan_slots(latest)
                links = latest.get("room_groups", {}).copy()
                placements = latest.get("wall_placements", {}).copy()
                names = latest.get("room_names", {}).copy()
                if wall_id not in slots or revision != plan_revision(latest, slots):
                    return web.json_response({"error": "project_conflict"}, status=409, headers=HEADERS)
                previous = slots[wall_id]
                if (previous == slot and "room_name" not in body and "room_group" not in body
                        and ("placement" not in body or placement == placements.get(wall_id))):
                    return overview_response(latest)
                if previous != slot:
                    occupant = next((other for other, value in slots.items() if value == slot), None)
                    if occupant is not None:
                        slots[occupant] = previous
                    slots[wall_id] = slot
                if "placement" in body:
                    if placement is None:
                        placements.pop(wall_id, None)
                    else:
                        placements[wall_id] = placement
                if "room_name" in body:
                    room = str(slot // 4)
                    if name:
                        names[room] = name
                    else:
                        names.pop(room, None)
                if "room_group" in body:
                    room = str(slot // 4)
                    links = {key: value for key, value in links.items() if key != room and value != group}
                    if group is not None:
                        links[room] = group
                data = {**latest, "plan_slots": slots, "wall_placements": placements,
                        "room_names": names, "room_groups": links}
                await asyncio.to_thread(store.write, path, data, PROJECT_LIMIT)
                state = data
                return overview_response(data)
        except invalid:
            return web.json_response({"error": "invalid_project"}, status=400, headers=HEADERS)
        except OSError:
            return web.json_response({"error": "project_storage_unavailable"}, status=503, headers=HEADERS)

    async def place_ceiling_light(request):
        nonlocal state
        try:
            body = await request.json()
            room, light, point = (body[key] for key in ("room", "light", "point"))
            if type(room) is not int or not 0 <= room < PLAN_SLOTS // 4:
                raise ValueError("Invalid room")
            light, _ = positions([[light, [50, 50] if point is None else point]])[0]
            async with lock:
                latest = await load()
                slots = plan_slots(latest)
                if body["revision"] != plan_revision(latest, slots):
                    return web.json_response({"error": "project_conflict"}, status=409, headers=HEADERS)
                if not any(slot // 4 == room for slot in slots.values()):
                    raise ValueError("Unknown room")
                ceilings = latest.get("ceiling_lights", {}).copy()
                points = dict(ceilings.get(str(room), []))
                if point is None:
                    points.pop(light, None)
                else:
                    points[light] = point
                ceilings[str(room)] = positions(list([key, value] for key, value in points.items()))
                data = {**latest, "ceiling_lights": ceilings}
                await asyncio.to_thread(store.write, path, data, PROJECT_LIMIT)
                state = data
                return overview_response(data)
        except invalid:
            return web.json_response({"error": "invalid_project"}, status=400, headers=HEADERS)
        except OSError:
            return web.json_response({"error": "project_storage_unavailable"}, status=503, headers=HEADERS)

    async def place_room(request):
        nonlocal state
        try:
            body = await request.json()
            room, x, z = (body[key] for key in ("room", "x_m", "z_m"))
            if (type(room) is not int or not 0 <= room < PLAN_SLOTS // 4
                    or any(type(value) not in (int, float) or not -40 <= value <= 40 for value in (x, z))):
                raise ValueError("Invalid room position")
            async with lock:
                latest = await load()
                slots = plan_slots(latest)
                if body["revision"] != plan_revision(latest, slots):
                    return web.json_response({"error": "project_conflict"}, status=409, headers=HEADERS)
                positions = {**latest.get("room_positions", {}), str(room): {"x_m": round(x, 2), "z_m": round(z, 2)}}
                data = {**latest, "room_positions": positions}
                await asyncio.to_thread(store.write, path, data, PROJECT_LIMIT)
                state = data
                return overview_response(data)
        except invalid:
            return web.json_response({"error": "invalid_project"}, status=400, headers=HEADERS)
        except OSError:
            return web.json_response({"error": "project_storage_unavailable"}, status=503, headers=HEADERS)

    async def place_tree(request):
        nonlocal state
        try:
            body = await request.json()
            room, tree = body["room"], body["tree"]
            if type(room) is not int or not 0 <= room < PLAN_SLOTS // 4:
                raise ValueError("Invalid room")
            placement = tree_placement(tree) if tree is not None else None
            async with lock:
                latest = await load()
                slots = plan_slots(latest)
                trees = latest.get("trees", {}).copy()
                key = str(room)
                if body["revision"] != plan_revision(latest, slots) or (
                    key not in trees and not any(slot // 4 == room for slot in slots.values())
                ):
                    return web.json_response({"error": "project_conflict"}, status=409, headers=HEADERS)
                if placement == trees.get(key):
                    return overview_response(latest)
                if placement is None:
                    trees.pop(key)
                else:
                    trees[key] = placement
                data = {**latest, "trees": trees}
                await asyncio.to_thread(store.write, path, data, PROJECT_LIMIT)
                state = data
                return overview_response(data)
        except invalid:
            return web.json_response({"error": "invalid_project"}, status=400, headers=HEADERS)
        except OSError:
            return web.json_response({"error": "project_storage_unavailable"}, status=503, headers=HEADERS)

    async def photo(request):
        try:
            layout = wall_layout(await current(), request.query.get("wall", DEFAULT_WALL))
            if layout["photo"] is None:
                raise web.HTTPNotFound()
            return web.Response(body=base64.b64decode(layout["photo"], validate=True),
                                content_type="image/jpeg", headers=HEADERS)
        except KeyError:
            raise web.HTTPNotFound()
        except (ValueError, OSError):
            raise web.HTTPServiceUnavailable()

    async def change(request):
        nonlocal state
        try:
            body = await request.json()
            action = body["action"]
            encoded = body.get("photo")
            wall_id = request.query.get("wall", DEFAULT_WALL)
            async with lock:
                latest = await load()
                walls = latest["walls"].copy()
                if wall_id != DEFAULT_WALL and wall_id not in walls:
                    raise web.HTTPConflict()
                shows = latest["shows"].copy()
                layout = wall_layout(latest, wall_id)
                data = {**latest, "shows": shows, "walls": walls}
                if action == "add_wall":
                    if len(walls) >= MAX_WALLS - 1:
                        raise web.HTTPConflict()
                    wall_id = uuid.uuid4().hex
                    walls[wall_id] = {**empty_layout(), "name": wall_name(body), "revision": uuid.uuid4().hex}
                elif action in ("rename_wall", "delete_wall"):
                    if body["revision"] != layout["revision"]:
                        raise web.HTTPConflict()
                    if action == "rename_wall":
                        update_wall_layout(data, wall_id, {**layout, "name": wall_name(body), "revision": uuid.uuid4().hex})
                    elif wall_id != DEFAULT_WALL:
                        saved = plan_slots(latest)
                        del saved[wall_id]
                        data["plan_slots"] = saved
                        placements = latest.get("wall_placements", {}).copy()
                        placements.pop(wall_id, None)
                        data["wall_placements"] = placements
                        del walls[wall_id]
                        wall_id = DEFAULT_WALL
                    else:
                        raise ValueError("Cannot delete primary wall")
                elif action == "save":
                    show_id = body.get("id")
                    show = show_settings(body)
                    if not lighting.valid_show(show):
                        raise ValueError("Unavailable scene")
                    if show_id is None:
                        if len(shows) >= MAX_SHOWS:
                            raise web.HTTPConflict()
                        show_id = uuid.uuid4().hex
                    elif shows[identifier(show_id)]["revision"] != body.get("revision"):
                        raise web.HTTPConflict()
                    shows[show_id] = {**show, "id": show_id, "revision": uuid.uuid4().hex}
                elif action == "delete":
                    show_id = identifier(body["id"])
                    if shows[show_id]["revision"] != body.get("revision"):
                        raise web.HTTPConflict()
                    del shows[show_id]
                elif action == "wall_dimensions":
                    if body["revision"] != layout["revision"]:
                        raise web.HTTPConflict()
                    update_wall_layout(data, wall_id, {**layout, "dimensions": wall_dimensions(body),
                                                       "revision": uuid.uuid4().hex})
                elif action == "layout":
                    if body["revision"] != layout["revision"]:
                        raise web.HTTPConflict()
                    current_photo = layout["photo"]
                    photo_version = layout["photo_version"]
                    if "photo" in body:
                        current_photo = await asyncio.to_thread(photo_jpeg, encoded) if encoded is not None else None
                        photo_version = uuid.uuid4().hex if current_photo is not None else None
                    points = positions(body["points"])
                    if points and current_photo is None and not layout.get("dimensions"):
                        raise ValueError("Positions require a photo or wall dimensions")
                    update_wall_layout(data, wall_id, {**layout, "revision": uuid.uuid4().hex,
                                      "photo_version": photo_version, "photo": current_photo, "points": points})
                elif action == "import":
                    entries = body["shows"]
                    if not isinstance(entries, list) or len(entries) > MAX_SHOWS:
                        raise ValueError("Invalid import")
                    imported = [show_settings(entry) for entry in entries]
                    for show in imported:
                        if any(all(existing[key] == value for key, value in show.items()) for existing in shows.values()):
                            continue
                        if len(shows) >= MAX_SHOWS:
                            raise web.HTTPConflict()
                        show_id = uuid.uuid4().hex
                        shows[show_id] = {**show, "id": show_id, "revision": uuid.uuid4().hex}
                    if encoded is not None and layout["photo"] is None:
                        update_wall_layout(data, wall_id, {**layout, "revision": uuid.uuid4().hex,
                                          "photo_version": uuid.uuid4().hex,
                                          "photo": await asyncio.to_thread(photo_jpeg, encoded),
                                          "points": positions(body["points"])})
                elif action == "preview_music":
                    playback.preview_music(music_settings(body["music"]))
                    return response(data, wall_id)
                elif action == "play":
                    playback.start(shows[identifier(body["id"])])
                    return response(data, wall_id)
                elif action == "spatial":
                    effect = body.get("effect")
                    direction = body.get("direction", "right") if effect is not None else body["direction"]
                    color, delay = rgb(body["color"]), body["delay"]
                    if ((effect is not None and effect not in RADIAL_EFFECTS) or direction not in DIRECTIONS
                            or not any(color) or type(delay) is not int
                            or not 250 <= delay <= 2000 or not layout["points"]):
                        raise ValueError("Invalid spatial effect")
                    if body["revision"] != layout["revision"]:
                        raise web.HTTPConflict()
                    end_color = rgb(body["end_color"]) if "end_color" in body else None
                    if end_color is not None and (effect or not any(end_color)):
                        raise ValueError("Invalid end color")
                    playback.start_spatial(layout["points"], direction, color, delay, end_color, effect)
                    return response(data, wall_id)
                elif action == "stop":
                    playback.request_stop()
                    return response(data, wall_id)
                else:
                    raise ValueError("Invalid action")
                await asyncio.to_thread(store.write, path, data, PROJECT_LIMIT)
                state = data
                return response(data, wall_id, imported_photo=action == "import" and wall_layout(data, wall_id) is not layout)
        except invalid:
            return web.json_response({"error": "invalid_project"}, status=400, headers=HEADERS)
        except OSError:
            return web.json_response({"error": "project_storage_unavailable"}, status=503, headers=HEADERS)
        except web.HTTPConflict:
            return web.json_response({"error": "project_conflict"}, status=409, headers=HEADERS)

    async def get_music_players(request):
        try:
            players = await music_assistant_players()
        except (ClientError, TimeoutError, ValueError) as exc:
            raise web.HTTPBadGateway() from exc
        return web.json_response({"players": players}, headers=HEADERS)

    app.router.add_get("/lighting/projects/music-players", get_music_players)
    app.router.add_get("/lighting/projects", get)
    app.router.add_post("/lighting/projects", change)
    app.router.add_get("/lighting/projects/photo", photo)
    app.router.add_get("/lighting/projects/overview", overview)
    app.router.add_post("/lighting/projects/overview", move_wall)
    app.router.add_post("/lighting/projects/overview/tree", place_tree)
    app.router.add_post("/lighting/projects/overview/room", place_room)
    app.router.add_post("/lighting/projects/overview/ceiling", place_ceiling_light)
    app.cleanup_ctx.append(playback.cleanup)
    app.cleanup_ctx.append(voice_events)
