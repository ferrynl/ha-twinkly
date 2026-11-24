"""Server-side Hue Entertainment effects using a paired Bridge."""
import asyncio
import colorsys
import logging
import math
import uuid

from aiohttp import ClientError

RESOURCE = "entertainment_configuration"
BRIDGE_ERRORS = (ClientError, OSError, RuntimeError, ValueError)
EFFECTS = {"rainbow", "sunset"}
LOGGER = logging.getLogger(__name__)


class EntertainmentError(Exception):
    def __init__(self, code, status):
        super().__init__(code)
        self.code = code
        self.status = status


def channel_ids(area):
    return sorted({channel["channel_id"] for channel in area.get("channels", [])
                   if type(channel.get("channel_id")) is int
                   and 0 <= channel["channel_id"] <= 255})


def music_area(areas, lights, services, targets):
    """Choose the largest area whose channels all belong to the requested lights."""
    by_device = {}
    for light in lights:
        owner = (light.get("owner") or {}).get("rid")
        if owner:
            by_device.setdefault(owner, set()).add(light["id"])
    by_service = {service["id"]: by_device.get((service.get("owner") or {}).get("rid"), set())
                  for service in services}
    best, matched = None, set()
    for area in areas:
        channels = area.get("channels", [])
        if not channels or len(channel_ids(area)) != len(channels):
            continue
        if not all(channel.get("members") for channel in channels):
            continue
        members = [by_service.get((member.get("service") or {}).get("rid"), set())
                   for channel in channels for member in channel["members"]]
        if not all(len(lights) == 1 for lights in members):
            continue
        covered = set.union(*members)
        if covered <= targets and len(covered) > len(matched):
            best, matched = area, covered
    return best, matched


def music_frame(frame, channels, level):
    from hue_entertainment import LightColorCommand

    count = len(frame) // 3 if frame else 0
    gain = 257 * level / 100
    commands = []
    for index, channel in enumerate(channels):
        start = index * count // len(channels)
        end = max(start + 1, (index + 1) * count // len(channels))
        color = max((frame[3 * pixel:3 * pixel + 3] for pixel in range(start, min(end, count))),
                    key=sum, default=(0, 0, 0))
        commands.append(LightColorCommand(channel, *(round(value * gain) for value in color)))
    return commands


def effect_frame(effect, elapsed, channels, brightness):
    from hue_entertainment import LightColorCommand

    level = 65535 * brightness / 100
    commands = []
    for index, channel in enumerate(channels):
        position = index / len(channels)
        if effect == "rainbow":
            color = colorsys.hsv_to_rgb((elapsed / 12 + position) % 1, 1, 1)
        else:
            wave = (1 + math.sin(elapsed * math.tau / 8 + position * math.tau)) / 2
            color = (0.65 + 0.35 * wave, 0.10 + 0.30 * wave, 0.025 + 0.10 * (1 - wave))
        red, green, blue = (round(component * level) for component in color)
        commands.append(LightColorCommand(channel, red, green, blue))
    return commands


def new_streamer():
    from hue_entertainment import HueDtlsStreamer

    return HueDtlsStreamer()


class HueEntertainment:
    def __init__(self, streamer_factory=new_streamer):
        self.streamer_factory = streamer_factory
        self.active = None
        self.error = None
        self.released = None
        self.task = None
        self.stop_event = asyncio.Event()

    @property
    def active_bridge(self):
        return self.active["bridge"] if self.active else None

    @property
    def music_active(self):
        return bool(self.active and self.active["effect"] == "music")

    def status(self):
        result = {"active": self.active, "error": self.error}
        if self.released is not None:
            result["released"] = self.released
        return result

    async def areas(self, identifier, record, hue):
        result = {"bridge": identifier, "address": record["address"],
                  "has_client_key": bool(record.get("client_key")), "areas": []}
        try:
            resources = await hue.request("GET", RESOURCE)
        except BRIDGE_ERRORS:
            return {**result, "unavailable": True}
        for area in resources:
            if not channel_ids(area):
                continue
            name = (area.get("metadata") or {}).get("name") or area.get("name") or area["id"]
            result["areas"].append({"id": area["id"], "name": name,
                                    "busy": area.get("status") == "active"})
        return result

    async def start(self, identifier, record, hue, area_id, effect, brightness):
        self.check_bridge(record)
        if (not isinstance(area_id, str) or str(uuid.UUID(area_id)) != area_id
                or not isinstance(effect, str) or effect not in EFFECTS
                or type(brightness) is not int or not 1 <= brightness <= 100):
            raise ValueError("Invalid Hue effect settings")
        resources = await self.idle_areas(hue)
        area = next((resource for resource in resources if resource.get("id") == area_id), None)
        if area is None or not (channels := channel_ids(area)):
            raise EntertainmentError("missing_area", 404)
        await self.open(identifier, record, hue, area_id, effect, brightness,
                        lambda elapsed: effect_frame(effect, elapsed, channels, brightness))

    def check_bridge(self, record):
        if self.active:
            raise EntertainmentError("busy", 409)
        if not record.get("client_key"):
            raise EntertainmentError("pair_again", 409)

    async def idle_areas(self, hue):
        resources = await hue.request("GET", RESOURCE)
        if any(resource.get("status") == "active" for resource in resources):
            raise EntertainmentError("busy", 409)
        return resources

    async def start_music(self, identifier, record, hue, targets, frame, level):
        self.check_bridge(record)
        areas = await self.idle_areas(hue)
        if not any(channel_ids(area) for area in areas):
            raise EntertainmentError("missing_area", 404)
        lights = await hue.lights()
        services = await hue.request("GET", "entertainment")
        area, covered = music_area(areas, lights, services, targets)
        if area is None:
            raise EntertainmentError("missing_area", 404)
        area_id = area["id"]
        if str(uuid.UUID(area_id)) != area_id:
            raise ValueError("Invalid Hue area ID")
        channels = channel_ids(area)
        await self.open(identifier, record, hue, area_id, "music", level(),
                        lambda _: music_frame(frame(), channels, level()))
        return covered, (area.get("metadata") or {}).get("name") or area.get("name") or area_id

    async def open(self, identifier, record, hue, area_id, effect, brightness, render):
        self.error = None
        self.released = None
        path = RESOURCE + "/" + area_id
        streamer = self.streamer_factory()
        await hue.request("PUT", path, {"action": "start"})
        try:
            connect = asyncio.create_task(asyncio.to_thread(
                streamer.connect, record["address"], record["application_key"],
                record["client_key"], area_id,
            ))
            try:
                await asyncio.shield(connect)
            except asyncio.CancelledError:
                await asyncio.gather(connect, return_exceptions=True)
                raise
            if not streamer.is_connected:
                raise RuntimeError("Hue DTLS handshake failed")
        except BaseException:
            await self.release(hue, path, streamer)
            raise

        self.active = {"bridge": identifier, "area": area_id, "effect": effect,
                       "brightness": brightness}
        self.stop_event.clear()
        self.task = asyncio.create_task(self.run(hue, path, streamer, render))

    async def run(self, hue, path, streamer, render):
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            while not self.stop_event.is_set():
                if not streamer.is_connected:
                    raise RuntimeError("Hue stream disconnected")
                streamer.send_colors(render(loop.time() - started))
                try:
                    await asyncio.wait_for(self.stop_event.wait(), 1 / 25)
                except TimeoutError:
                    pass
        except Exception:
            self.error = "stream_lost"
            LOGGER.warning("Hue Entertainment stream ended unexpectedly")
        finally:
            try:
                await self.release(hue, path, streamer)
            finally:
                self.active = None

    async def release(self, hue, path, streamer):
        try:
            await asyncio.to_thread(streamer.disconnect)
        finally:
            try:
                await hue.request("PUT", path, {"action": "stop"})
                area_id = path.rsplit("/", 1)[-1]
                for attempt in range(3):
                    areas = await hue.request("GET", path)
                    if any(area.get("id") == area_id and area.get("status") == "inactive" for area in areas):
                        self.released = area_id
                        break
                    if attempt < 2:
                        await asyncio.sleep(.25)
                if self.released is None:
                    raise RuntimeError("Hue Entertainment area did not become inactive")
            except BRIDGE_ERRORS:
                self.error = "stop_failed"
                LOGGER.warning("Hue Entertainment Bridge did not confirm stop")

    async def stop(self):
        if self.task:
            self.stop_event.set()
            await asyncio.shield(self.task)
            self.task = None

    async def cleanup(self, app):
        yield
        await self.stop()
