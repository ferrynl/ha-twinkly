import asyncio
import base64
import hashlib
import uuid
import colorsys
import math
from requests.exceptions import HTTPError
from xled.exceptions import ApplicationError
import functools
import io
import ipaddress
import json
import logging
import re
import socket
import struct
import time
from pathlib import Path

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from PIL import Image
from xled import HighControlInterface

DATA = Path("/data/devices.json")
GROUPS = DATA.with_name("groups.json")
MUSIC_STATE = DATA.with_name("music-state.json")
SHOW_STATE = DATA.with_name("show-state.json")
SILENCE_MODES = ("restore", "warm", "fade")
IMAGES = DATA.with_name("effect-images")
PRODUCT_PHOTOS = DATA.with_name("product-photos")
PRODUCT_PHOTO_URLS = {
    "strings-rgbw": "https://twinkly.com/cdn/shop/files/TWS250SPP-BEU_Out-of-the-box.jpg?v=1769612111&width=480",
    "line": "https://twinkly.com/cdn/shop/files/TWL100STW-BEU_Out-of-the-box.jpg?v=1757667667&width=480",
}
PIXELS = 120
FRAME_BYTES = PIXELS * 3
MAX_DEVICES = 40
MUSIC_STYLES = frozenset(('energy', 'spectrum', 'power', 'wavelength', 'strobe', 'scroll', 'bands', 'blade_power_plus', 'magnitude', 'fire'))
LOG = logging.getLogger("twinkly")


def local_ip(value):
    ip = ipaddress.IPv4Address(value)
    if not ip.is_private or ip.is_multicast or ip.is_unspecified:
        raise ValueError("Gebruik een lokaal IPv4-adres.")
    return str(ip)


def discover(broadcast):
    found = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(b"\x01discover", (broadcast, 5555))
        deadline = time.monotonic() + 2
        while len(found) < MAX_DEVICES and time.monotonic() < deadline:
            sock.settimeout(max(0.001, deadline - time.monotonic()))
            try:
                packet, (host, _) = sock.recvfrom(256)
            except TimeoutError:
                break
            if packet[4:6] == b"OK":
                found.add(host)
    return sorted(found)


class DDP(asyncio.DatagramProtocol):
    def __init__(self, source):
        self.source = source
        self.frame = None
        self.received = 0.0
        self.lit_at = 0.0
        self.buffer = bytearray(FRAME_BYTES)
        self.size = 0

    def datagram_received(self, packet, addr):
        if addr[0] != self.source or len(packet) < 10:
            return
        flags, _, dtype, target, offset, count = struct.unpack("!BBBBIH", packet[:10])
        if flags & 0xfe != 0x40 or dtype not in (1, 0x0b) or target != 1:
            return
        if offset == 0:
            self.size = 0
        if offset != self.size or count == 0 or len(packet) != 10 + count:
            self.size = 0
            return
        end = offset + count
        if end > FRAME_BYTES:
            self.size = 0
            return
        self.buffer[offset:end] = packet[10:]
        self.size = end
        if flags & 1:
            if end == FRAME_BYTES:
                self.frame = bytes(self.buffer)
                self.received = time.monotonic()
                if any(self.frame):
                    self.lit_at = self.received
            self.size = 0


def realtime_packets(payload, token, version, led_count):
    if version == 1:
        yield b"\x01" + token + bytes([led_count]) + payload
    elif version == 2:
        yield b"\x02" + token + b"\x00" + payload
    else:
        for offset in range(0, len(payload), 900):
            yield b"\x03" + token + b"\x00\x00" + bytes([offset // 900]) + payload[offset:offset + 900]


class Device:
    def __init__(self, row, limit, realtime_socket):
        self.row = row
        self.limit = limit
        self.realtime_socket = realtime_socket
        self.lock = asyncio.Lock()
        self.client = self.connect()
        self.restore = None
        self.last_mode = None
        self.mode = None
        self.mode_check = 0.0
        self.effects = []
        self.effects_until = 0.0
        self.layout = None
        self.layout_until = 0.0
        self.product_code = row.get('product_code')
        self.model_checked = bool(self.product_code)
        self.details = None
        self.details_until = 0.0
        self.rt_check = 0.0
        self.retry = 0.0
        self.error = None
        self.mapping = tuple(3 * (i * PIXELS // row["leds"]) for i in range(row["leds"]))

    def connect(self):
        client = HighControlInterface(self.row["ip"])
        client.session.trust_env = False
        client.session.request = functools.partial(client.session.request, timeout=(1, 2))
        return client

    def api(self, path, payload=None):
        session = self.client.session
        try:
            response = session.get(path) if payload is None else session.post(path, json=payload)
        except AssertionError as exc:
            raise ValueError(f'{path}: XLED kon de sessie of het antwoord niet valideren') from exc
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 1000:
            raise ApplicationError(f"{path}: Twinkly code {data.get('code')}", response=response)
        return data

    def read_mode(self):
        self.mode = self.api("led/mode").get("mode")
        self.mode_check = time.monotonic() + 30
        return self.mode

    def set_mode(self, mode):
        self.api("led/mode", {"mode": mode})
        self.mode = mode
        self.mode_check = time.monotonic() + 30

    def color(self, rgb):
        hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
        self.api("led/color", {"hue": round(hue * 360) % 360,
                               "saturation": round(saturation * 255), "value": round(value * 255)})
        self.set_mode("color")

    def turn_on(self):
        for mode in dict.fromkeys((self.last_mode, "color", "demo", "effect", "playlist", "movie")):
            if mode is None:
                continue
            try:
                if mode == "color" and self.last_mode is None:
                    self.color((255, 190, 110))
                    self.last_mode = mode
                    return
                self.set_mode(mode)
                self.last_mode = mode
                return
            except (ApplicationError, HTTPError):
                continue
        self.color((255, 190, 110))
        self.last_mode = "color"

    def read_product_code(self):
        info = self.api("gestalt")
        self.product_code = info.get("product_code")
        self.model_checked = True

    def load_details(self):
        if time.monotonic() < self.details_until:
            return
        info = self.api("gestalt")
        self.product_code = info.get("product_code") or self.product_code
        self.model_checked = True
        details = {key: info[key] for key in (
            "product_name", "product_code", "product_version", "hardware_version",
            "firmware_version", "fw_family", "led_type", "led_version", "wire_type",
            "hw_id", "mac", "uuid", "uptime", "flash_size", "max_supported_led",
            "base_leds_number", "number_of_led", "led_profile", "bytes_per_led",
            "frame_rate", "movie_capacity", "rssi",
        ) if key in info}
        for path in ("fw/version", "network/status"):
            try:
                data = self.api(path)
            except (HTTPError, ApplicationError, ValueError):
                continue
            if path == "fw/version":
                details["firmware_version"] = data.get("version") or details.get("firmware_version")
            else:
                station = data.get("station") or {}
                access_point = data.get("ap") or {}
                details.update({key: station[key] for key in ("ssid", "ip", "gw", "mask", "status")
                                if key in station})
                details["network_mode"] = data.get("mode")
                details["rssi"] = station.get("rssi", data.get("rssi", details.get("rssi")))
                channel = station.get("channel") or data.get("channel")
                if channel is None and data.get("mode") == 0:
                    channel = access_point.get("channel")
                details["channel"] = channel
        self.details = {key: value for key, value in details.items()
                        if isinstance(value, (str, int, float, bool)) and value != ""}
        self.details_until = time.monotonic() + 60

    def load_layout(self):
        if time.monotonic() < self.layout_until:
            return
        data = self.api("led/layout/full")
        points = []
        for index, point in enumerate((data.get("coordinates") or [])[:4096]):
            if not isinstance(point, dict):
                continue
            coords = [point.get(axis, 0 if axis == "z" else None) for axis in ("x", "y", "z")]
            if all(type(value) in (int, float) and math.isfinite(value) for value in coords):
                points.append([index, *coords])
        self.layout = {"points": points, "source": data.get("source"),
                       "synthesized": data.get("synthesized") is True}
        self.layout_until = time.monotonic() + 120

    def load_effects(self):
        if time.monotonic() < self.effects_until:
            return
        catalog = []
        for path, kind in (("movies", "movie"), ("led/effects", "effect")):
            try:
                data = self.api(path)
            except HTTPError as exc:
                if exc.response.status_code not in (400, 404, 405, 501):
                    raise
                continue
            except ApplicationError:
                continue
            if kind == "movie":
                catalog.extend({"kind": kind, "id": item["id"], "name": item.get("name", "")}
                               for item in data.get("movies", []) if type(item.get("id")) is int)
            else:
                catalog.extend({"kind": kind, "id": index, "name": ""}
                               for index in range(min(256, int(data.get("effects_number", 0)))))
        self.effects = catalog
        self.effects_until = time.monotonic() + 120

    def command(self, action, value):
        if action == "stop":
            if self.restore is not None:
                self.set_mode(self.restore)
                self.restore = None
            return
        if action == "music":
            return
        self.command("stop", None)
        if action == "on":
            self.turn_on()
        elif action == "off":
            try:
                mode = self.api("led/mode").get("mode")
                if mode in ("playlist", "movie", "effect", "demo", "color"):
                    self.last_mode = mode
            except (HTTPError, ApplicationError):
                pass
            self.set_mode("off")
        elif action == "color":
            self.color(value)
            self.last_mode = "color"
        elif action == "effect":
            kind, index = value
            if kind == "movie":
                try:
                    self.api("movies/current", {"id": index})
                except HTTPError as exc:
                    if exc.response.status_code not in (404, 405):
                        raise
                    self.api("led/movies/current", {"id": index})
            else:
                self.api("led/effects/current", {"effect_id": index})
            self.set_mode(kind)
            self.last_mode = kind
        elif action == "brightness":
            self.client.set_brightness(value).raise_for_status()

    def send(self, frame):
        now = time.monotonic()
        if now >= self.rt_check:
            mode = self.read_mode()
            if self.restore is None:
                self.restore = mode if mode != "rt" else "off"
            if mode != "rt":
                self.set_mode("rt")
            self.rt_check = now + 2
        # RGBW controllers use white first on the realtime wire.
        white = b"\0" if self.row["profile"] == "RGBW" else b""
        payload = b"".join(white + frame[i:i + 3] for i in self.mapping)
        token = base64.b64decode(self.client.session.access_token)
        packets = realtime_packets(payload, token, self.row["protocol"], self.row["leds"])
        for packet in packets:
            self.realtime_socket.sendto(packet, (self.row["ip"], 7777))

    async def run(self, method, *args):
        async with self.lock, self.limit:
            try:
                await asyncio.to_thread(method, *args)
            except Exception as exc:
                self.error = str(exc) or type(exc).__name__
                self.retry = time.monotonic() + 5
                self.rt_check = 0
                self.client.session.close()
                self.client = self.connect()
                LOG.warning("%s: %s", self.row["ip"], exc)
                return False
            self.error = None
            return True


class Controller:
    def __init__(self, options):
        self.source = local_ip(options["ddp_source"])
        self.ddp = DDP(self.source)
        self.fps = options["fps"]
        self.broadcast = local_ip(options.get("discovery_broadcast", "255.255.255.255"))
        self.limit = asyncio.Semaphore(8)
        self.realtime_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.devices = {}
        self.show = (json.loads(SHOW_STATE.read_text(encoding="utf-8")) if SHOW_STATE.exists()
                     else {"master": 100, "scenes": {}})
        self.groups = json.loads(GROUPS.read_text(encoding='utf-8')) if GROUPS.exists() else {}
        self.music = set()
        self.edit = asyncio.Lock()
        self.music_setup = asyncio.Lock()
        self.active_style = (json.loads(MUSIC_STATE.read_text(encoding='utf-8')).get('style')
                             if MUSIC_STATE.is_file() else None)
        self.gif_capture = asyncio.Lock()
        self.photo_lock = asyncio.Lock()
        self.track_lock = asyncio.Lock()
        self.track_until = 0.0
        self.track_state = {'track': None, 'available': False}
        self.track_art = None
        self.track_art_cache = None
        self.probe = asyncio.Semaphore(6)
        if DATA.exists():
            for row in json.loads(DATA.read_text()):
                self.devices[row["id"]] = Device(row, self.limit, self.realtime_socket)

    @staticmethod
    def inspect(host):
        client = HighControlInterface(host)
        with client.session as session:
            session.trust_env = False
            session.request = functools.partial(session.request, timeout=(1, 2))
            info = client.get_device_info()
            info.raise_for_status()
            leds = int(info["number_of_led"])
            profile = str(info["led_profile"]).replace("+", "").upper()
            if not 1 <= leds <= 4096 or profile not in ("RGB", "RGBW"):
                raise ValueError("Onbekend ledprofiel of aantal leds")
            return {"id": str(info.get("mac") or info.get("hw_id") or host),
                    "name": str(info.get("device_name") or host), "ip": host,
                    "leds": leds, "profile": profile, "product_code": info.get("product_code"),
                    "protocol": 1 if str(info.get("product_version")) == "1" and leds <= 255 else 3}

    async def add(self, host):
        async with self.probe:
            row = await asyncio.to_thread(self.inspect, local_ip(host))
        async with self.edit:
            key = row["id"]
            old = self.devices.get(key)
            if old and old.row == row:
                return row
            if not old and len(self.devices) >= MAX_DEVICES:
                raise ValueError("Maximum aantal apparaten bereikt")
            if old:
                self.music.discard(key)
                await old.run(old.command, "stop", None)
                old.client.session.close()
            self.devices[key] = Device(row, self.limit, self.realtime_socket)
            self.save()
        return row

    def save(self):
        temp = DATA.with_suffix(".tmp")
        temp.write_text(json.dumps([d.row for d in self.devices.values()]), encoding="utf-8")
        temp.replace(DATA)

    @staticmethod
    def dim_frame(frame, level):
        return frame if level == 100 else bytes(channel * level // 100 for channel in frame)

    def silence_mode(self, key):
        # For overlapping groups, the first configured non-default rule wins.
        return next((group["silence"] for group in self.groups.values()
                     if key in group["members"] and group.get("silence", "restore") != "restore"), "restore")

    async def output(self, device):
        key = device.row["id"]
        last_output = None
        fade_started = None
        while self.devices.get(key) is device:
            now = time.monotonic()
            armed = key in self.music
            active = (armed and self.ddp.frame is not None and now - self.ddp.received < 1.5
                      and now - self.ddp.lit_at < 3)
            fading = False
            if now >= device.retry:
                if active:
                    fade_started = None
                    frame = self.dim_frame(self.ddp.frame, self.show["master"])
                    if any(frame):
                        last_output = frame
                    await device.run(device.send, frame)
                elif device.restore is not None:
                    rule = self.silence_mode(key) if armed else "restore"
                    if rule == "fade" and last_output is not None:
                        fade_started = fade_started or now
                        remaining = max(0, 100 - int((now - fade_started) * 100))
                        if remaining:
                            fading = True
                            await device.run(device.send, self.dim_frame(last_output, remaining))
                        elif await device.run(device.set_mode, "off"):
                            device.restore = None
                    elif rule == "fade":
                        if await device.run(device.set_mode, "off"):
                            device.restore = None
                    elif rule == "warm":
                        if await device.run(device.color, (255, 190, 110)):
                            device.restore = None
                    else:
                        await device.run(device.command, "stop", None)
                    if not fading:
                        device.rt_check = 0
                        last_output = None
                        fade_started = None
                elif now >= device.mode_check:
                    device.mode_check = now + 30
                    if not await device.run(device.read_mode):
                        device.mode = None
                    elif not device.model_checked:
                        await device.run(device.read_product_code)
            await asyncio.sleep(1 / self.fps if active or fading else 0.2)

    async def stream(self, app):
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: self.ddp, local_addr=("127.0.0.1" if self.source == "127.0.0.1" else "0.0.0.0", 18490)
        )
        workers = {}

        async def supervise():
            while True:
                for key, (device, task) in list(workers.items()):
                    if self.devices.get(key) is not device:
                        await asyncio.gather(task, return_exceptions=True)
                        del workers[key]
                for key, device in self.devices.items():
                    if key not in workers:
                        workers[key] = device, asyncio.create_task(self.output(device))
                await asyncio.sleep(0.25)

        supervisor = asyncio.create_task(supervise())
        yield
        supervisor.cancel()
        await asyncio.gather(supervisor, return_exceptions=True)
        transport.close()
        # Let outstanding device operations finish before restoring modes.
        self.music.clear()
        await asyncio.gather(*(d.run(d.command, "stop", None) for d in self.devices.values()))
        for _, task in workers.values():
            task.cancel()
        await asyncio.gather(*(task for _, task in workers.values()), return_exceptions=True)
        self.realtime_socket.close()

    async def status(self, request):
        return web.json_response({
            "audio": self.ddp.frame is not None and time.monotonic() - self.ddp.received < 1.5,
            "groups": self.groups,
            "active_music_style": self.active_style,
            "show": self.show,
            "devices": [dict(d.row, music=k in self.music, mode=d.mode, error=d.error, product_code=d.product_code)
                        for k, d in self.devices.items()],
        })

    async def register(self, request):
        data = await request.json()
        async with self.edit_scan:
            hosts = [data["ip"]] if data.get("ip") else await asyncio.to_thread(discover, self.broadcast)
            if not hosts:
                return web.json_response({"added": 0, "errors": [
                    f"Geen UDP-antwoord via {self.broadcast}:5555. Probeer een IP-adres of stel het broadcastadres van je LAN in."
                ]})
            results = await asyncio.gather(*(self.add(host) for host in hosts), return_exceptions=True)
        return web.json_response({"added": sum(isinstance(x, dict) for x in results),
                                  "errors": [f"{host}: {result}" for host, result in zip(hosts, results)
                                             if isinstance(result, Exception)]})

    async def save_show(self, request):
        data = await request.json()
        async with self.edit:
            show = {"master": self.show["master"], "scenes": self.show["scenes"].copy()}
            scenes = show["scenes"]
            if "master" in data:
                level = data["master"]
                if type(level) is not int or not 0 <= level <= 100:
                    raise web.HTTPBadRequest()
                show["master"] = level
            elif "delete" in data:
                scene = data["delete"]
                if not isinstance(scene, str) or scene not in scenes:
                    raise web.HTTPNotFound()
                del scenes[scene]
            else:
                name, group = data.get("name"), data.get("group")
                style, level, mode = data.get("style"), data.get("level"), data.get("mode")
                if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
                        or not isinstance(group, str) or (group != "*" and group not in self.groups)
                        or not isinstance(style, str) or style not in MUSIC_STYLES
                        or type(level) is not int or not 0 <= level <= 100
                        or mode not in ("music", "off") or len(scenes) >= MAX_DEVICES):
                    raise web.HTTPBadRequest()
                scenes[uuid.uuid4().hex] = {"name": name.strip(), "group": group, "style": style,
                                           "level": level, "mode": mode}
            temp = SHOW_STATE.with_suffix(".tmp")
            temp.write_text(json.dumps(show), encoding="utf-8")
            temp.replace(SHOW_STATE)
            self.show = show
        return web.json_response({"ok": True})

    async def save_group(self, request):
        data = await request.json()
        group_id = data.get("id")
        async with self.edit:
            groups = self.groups.copy()
            if group_id is not None and (not isinstance(group_id, str) or group_id not in groups):
                raise web.HTTPNotFound()
            if data.get("delete") is True and group_id is not None:
                del groups[group_id]
            else:
                name, members = data.get("name"), data.get("members")
                if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
                        or not isinstance(members, list) or not 1 <= len(members) <= MAX_DEVICES
                        or any(not isinstance(key, str) or key not in self.devices for key in members)):
                    raise web.HTTPBadRequest()
                if group_id is None and len(groups) >= MAX_DEVICES:
                    raise web.HTTPBadRequest()
                silence = data.get("silence", "restore")
                if silence not in SILENCE_MODES:
                    raise web.HTTPBadRequest()
                groups[group_id or uuid.uuid4().hex] = {
                    "name": name.strip(), "members": list(dict.fromkeys(members)), "silence": silence
                }
            temp = GROUPS.with_suffix(".tmp")
            temp.write_text(json.dumps(groups), encoding="utf-8")
            temp.replace(GROUPS)
            self.groups = groups
        return web.json_response({"ok": True})

    @staticmethod
    def image_path(key, kind, index):
        fingerprint = hashlib.sha256(f"{key}/{kind}/{index}".encode()).hexdigest()
        return IMAGES / (fingerprint + ".jpg")

    async def product_photo(self, request):
        key = request.match_info["key"]
        url = PRODUCT_PHOTO_URLS.get(key)
        if url is None:
            raise web.HTTPNotFound()
        path = PRODUCT_PHOTOS / (key + ".jpg")
        if not path.is_file():
            async with self.photo_lock:
                if not path.is_file():
                    try:
                        async with ClientSession(timeout=ClientTimeout(total=8)) as session:
                            async with session.get(url, allow_redirects=False) as response:
                                if response.status != 200 or response.content_type != "image/jpeg":
                                    raise ValueError("Unexpected product photo response")
                                raw = bytearray()
                                async for chunk in response.content.iter_chunked(65536):
                                    raw.extend(chunk)
                                    if len(raw) > 1_000_000:
                                        raise ValueError("Product photo too large")
                                if not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
                                    raise ValueError("Invalid JPEG product photo")
                        PRODUCT_PHOTOS.mkdir(exist_ok=True)
                        temp = path.with_suffix(".tmp")
                        temp.write_bytes(raw)
                        temp.replace(path)
                    except (ClientError, TimeoutError, ValueError, OSError) as exc:
                        LOG.warning("Product photo %s: %s", key, exc)
                        raise web.HTTPBadGateway() from exc
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400",
                                               "X-Content-Type-Options": "nosniff"})

    async def effect_image(self, request):
        key = request.query.get("id")
        kind = request.query.get("kind")
        index = request.query.get("index", "")
        if key not in self.devices or kind not in ("movie", "effect") or not re.fullmatch(r"[0-9]{1,3}", index):
            raise web.HTTPNotFound()
        path = self.image_path(key, kind, int(index))
        if request.method == "GET":
            if not path.is_file():
                raise web.HTTPNotFound()
            return web.FileResponse(path, headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})
        data = await request.json()
        image = data.get("image")
        if image is None:
            path.unlink(missing_ok=True)
        else:
            try:
                raw = base64.b64decode(image, validate=True)
            except (ValueError, TypeError):
                raise web.HTTPBadRequest()
            if not 4 <= len(raw) <= 160_000 or not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
                raise web.HTTPBadRequest()
            IMAGES.mkdir(exist_ok=True)
            temp = path.with_suffix(".tmp")
            temp.write_bytes(raw)
            temp.replace(path)
        return web.json_response({"ok": True})

    async def control(self, request):
        data = await request.json()
        action = data.get("action")
        value = data.get("value")
        if action not in ("on", "off", "color", "brightness", "music", "stop", "effect"):
            raise web.HTTPBadRequest()
        if action == "color":
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise web.HTTPBadRequest()
            value = bytes.fromhex(value[1:])
        if action == "brightness" and (type(value) is not int or not 0 <= value <= 100):
            raise web.HTTPBadRequest()
        if action == "effect":
            if (not isinstance(value, list) or len(value) != 2
                    or value[0] not in ("movie", "effect") or type(value[1]) is not int
                    or not 0 <= value[1] <= 255 or data.get("id") == "*"):
                raise web.HTTPBadRequest()
        async with self.edit:
            group_id = data.get("group")
            if group_id is not None:
                if not isinstance(group_id, str) or group_id not in self.groups or action == "effect":
                    raise web.HTTPBadRequest()
                keys = self.groups[group_id]["members"]
            else:
                keys = list(self.devices) if data.get("id") == "*" else [data.get("id")]
            if any(key not in self.devices for key in keys):
                raise web.HTTPNotFound()
            if action == "music":
                self.music.update(keys)
                return web.json_response({"failed": []})
            self.music.difference_update(keys)
            results = await asyncio.gather(*(self.devices[k].run(self.devices[k].command, action, value)
                                             for k in keys))
            return web.json_response({"failed": [
                f"{self.devices[key].row['ip']}: {self.devices[key].error}"
                for key, ok in zip(keys, results) if not ok
            ]})

    async def details(self, request):
        device = self.devices.get(request.query.get("id"))
        if device is None:
            raise web.HTTPNotFound()
        ok = await device.run(device.load_details)
        return web.json_response({"details": device.details if ok else None,
                                  "error": None if ok else device.error})

    async def layout(self, request):
        device = self.devices.get(request.query.get("id"))
        if device is None:
            raise web.HTTPNotFound()
        ok = await device.run(device.load_layout)
        return web.json_response({"layout": device.layout if ok else None,
                                  "error": None if ok else device.error})

    async def effects(self, request):
        device = self.devices.get(request.query.get("id"))
        if device is None:
            raise web.HTTPNotFound()
        ok = await device.run(device.load_effects)
        catalog = [dict(entry, has_image=self.image_path(device.row["id"], entry["kind"], entry["id"]).is_file())
                   for entry in device.effects] if ok else []
        return web.json_response({"effects": catalog, "error": None if ok else device.error})

    async def now_playing(self, request):
        async with self.track_lock:
            now = time.monotonic()
            if now >= self.track_until:
                self.track_until = now + 3
                self.track_state = {"track": None, "available": False}
                self.track_art = None
                try:
                    async with ClientSession(timeout=ClientTimeout(total=2)) as session:
                        async with session.get("http://127.0.0.1:8888/api/now-playing",
                                               allow_redirects=False) as response:
                            response.raise_for_status()
                            data = await response.json()
                    self.track_state["available"] = True
                    metadata = data.get("metadata") or {}
                    if metadata.get("source_id") == "sendspin" and metadata.get("title"):
                        track = {key: str(metadata.get(key) or "")[:512]
                                 for key in ("title", "artist", "album")}
                        artwork = data.get("artwork") or {}
                        path = artwork.get("cache_key") or ""
                        digest = artwork.get("hash") or ""
                        if (re.fullmatch(r"now_playing/now_playing\.(jpg|jpeg|png|webp|gif)", path)
                                and re.fullmatch(r"[a-fA-F0-9]{8,128}", digest)):
                            self.track_art = (digest, path)
                            track["artwork"] = digest
                        self.track_state["track"] = track
                except (ClientError, TimeoutError, ValueError):
                    self.track_until = now + 10
            return web.json_response(self.track_state, headers={"Cache-Control": "no-store"})

    async def now_playing_art(self, request):
        async with self.track_lock:
            if self.track_art is None or request.query.get("v") != self.track_art[0]:
                raise web.HTTPNotFound()
            if self.track_art_cache is None or self.track_art_cache[0] != self.track_art:
                try:
                    async with ClientSession(timeout=ClientTimeout(total=3)) as session:
                        async with session.get("http://127.0.0.1:8888/api/assets/download",
                                               params={"path": self.track_art[1]}, allow_redirects=False) as response:
                            if response.status != 200 or response.content_type not in (
                                "image/jpeg", "image/png", "image/webp", "image/gif"
                            ):
                                raise web.HTTPNotFound()
                            content = bytearray()
                            async for chunk in response.content.iter_chunked(65536):
                                content.extend(chunk)
                                if len(content) > 2_000_000:
                                    raise web.HTTPNotFound()
                            self.track_art_cache = (self.track_art, bytes(content), response.content_type)
                except (ClientError, TimeoutError) as exc:
                    raise web.HTTPBadGateway() from exc
            _, content, mime = self.track_art_cache
            return web.Response(body=content, content_type=mime,
                                headers={"Cache-Control": "private, max-age=86400",
                                         "X-Content-Type-Options": "nosniff"})

    def music_frame(self):
        if time.monotonic() - self.ddp.received < 1.5:
            return self.ddp.frame
        return None

    async def music_preview(self, request):
        frame = self.music_frame()
        return web.Response(body=self.dim_frame(frame, self.show['master']) if frame else b"",
                            content_type="application/octet-stream",
                            headers={"Cache-Control": "no-store"})

    @staticmethod
    def encode_gif(frames):
        images = [Image.frombytes("RGB", (PIXELS, 1), frame)
                  .resize((PIXELS * 3, 64), Image.Resampling.NEAREST)
                  .quantize(colors=128) for frame in frames]
        with io.BytesIO() as output:
            images[0].save(output, format="GIF", save_all=True,
                           append_images=images[1:], duration=100, loop=0)
            return output.getvalue()

    async def music_gif(self, request):
        if self.gif_capture.locked():
            raise web.HTTPConflict()
        async with self.gif_capture:
            frames = []
            for _ in range(30):
                frame = self.music_frame()
                if frame is None:
                    raise web.HTTPServiceUnavailable()
                frames.append(frame)
                await asyncio.sleep(0.1)
            result = await asyncio.to_thread(self.encode_gif, frames)
        return web.Response(body=result, content_type="image/gif", headers={"Cache-Control": "no-store"})

    async def setup_music(self, request):
        data = await request.json()
        style = data.get("style") if isinstance(data, dict) else None
        if style is not None and (not isinstance(style, str) or style not in MUSIC_STYLES):
            raise web.HTTPBadRequest()
        if self.source != "127.0.0.1":
            return web.json_response({"message": "Automatische koppeling vereist LedFX op dezelfde Home Assistant-host en ddp_source 127.0.0.1."})
        async with self.music_setup:
            try:
                async with ClientSession(base_url="http://127.0.0.1:8888", timeout=ClientTimeout(total=10)) as session:
                    active_style = await configure_ledfx(session, style)
                self.active_style = active_style
                temp = MUSIC_STATE.with_suffix('.tmp')
                temp.write_text(json.dumps({'style': active_style}), encoding='utf-8')
                temp.replace(MUSIC_STATE)
            except (ClientError, TimeoutError, ValueError, KeyError, OSError) as exc:
                LOG.warning("LedFX setup: %s", exc)
                return web.json_response({"message": f"LedFX koppelen mislukt: {exc or type(exc).__name__}"})
        return web.json_response({
            "ok": True,
            "message": "LedFX ingesteld. Voeg LedFx Twinkly toe aan de afspeelgroep in Music Assistant en start muziek."
        })

    def app(self):
        self.edit_scan = asyncio.Lock()
        app = web.Application(middlewares=[ingress_only], client_max_size=240_000)
        app.cleanup_ctx.append(self.stream)
        app.router.add_get("/", lambda _: web.FileResponse("index.html"))
        app.router.add_get("/status", self.status)
        app.router.add_get("/effects", self.effects)
        app.router.add_get("/layout", self.layout)
        app.router.add_get("/details", self.details)
        app.router.add_post("/register", self.register)
        app.router.add_post("/control", self.control)
        app.router.add_post("/groups", self.save_group)
        app.router.add_post("/show", self.save_show)
        app.router.add_get("/product-photo/{key}", self.product_photo)
        app.router.add_get("/effect-image", self.effect_image)
        app.router.add_post("/effect-image", self.effect_image)
        app.router.add_post("/setup-music", self.setup_music)
        app.router.add_get("/music-preview", self.music_preview)
        app.router.add_get("/now-playing", self.now_playing)
        app.router.add_get("/now-playing-art", self.now_playing_art)
        app.router.add_post("/music-gif", self.music_gif)
        return app


async def configure_ledfx(session, style=None):
    async def api(method, path, body=None):
        async with session.request(method, "/api" + path, json=body, allow_redirects=False) as response:
            data = await response.json()
            if response.status >= 300 or data.get("status") in ("failed", "error"):
                reason = data.get("payload", {}).get("reason", f"HTTP {response.status}")
                raise ValueError(f"{path}: {reason}")
            return data

    info = await api("GET", "/info")
    if not info.get("features", {}).get("sendspin"):
        raise ValueError("Deze LedFX-engine biedt geen Sendspin.")

    server_id = "twinkly-music"
    servers = (await api("GET", "/sendspin/servers"))["servers"]
    if server_id not in servers:
        scan = await api("GET", "/sendspin/discover?timeout=3")
        found = scan.get("data", {}).get("servers", scan.get("servers", []))
        urls = {server["server_url"] for server in found}
        if len(urls) > 1:
            raise ValueError("Meerdere Sendspin-servers gevonden. Kies er één in LedFX.")
        server_url = next(iter(urls), "ws://127.0.0.1:8927/sendspin")
        await api("POST", "/sendspin/servers", {
            "id": server_id, "server_url": server_url, "client_name": "LedFx Twinkly"
        })

    audio = await api("GET", "/audio/devices")
    index = next((int(key) for key, name in audio["devices"].items()
                  if name == f"SENDSPIN: {server_id}"), None)
    if index is None:
        raise ValueError("De Sendspin-bron verschijnt niet in de LedFX-audiolijst.")
    if index != audio.get("active_device_index"):
        await api("PUT", "/audio/devices", {"audio_device": index})

    config = {"name": "Twinkly Kerst", "ip_address": "127.0.0.1", "port": 18490,
              "pixel_count": PIXELS, "destination_id": 1}
    devices = (await api("GET", "/devices"))["devices"]
    device = next((item for item in devices.values() if item["type"] == "ddp"
                   and all(item["config"].get(key) == value
                           for key, value in config.items() if key != "name")), None)
    if device is None:
        device = (await api("POST", "/devices", {"type": "ddp", "config": config}))["device"]

    path = f"/virtuals/{device['id']}/effects"
    active = (await api("GET", path)).get("effect") or {}
    if not active or (style and style != active.get("type")):
        active_style = style or "energy"
        await api("POST", path, {"type": active_style, "config": {}})
        return active_style
    return active.get("type")


@web.middleware
async def ingress_only(request, handler):
    if request.remote != "172.30.32.2":
        raise web.HTTPForbidden()
    if request.method == "POST" and request.content_type != "application/json":
        raise web.HTTPUnsupportedMediaType()
    return await handler(request)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    options = json.loads(Path("/data/options.json").read_text())
    web.run_app(Controller(options).app(), host="0.0.0.0", port=18489, access_log=None)
