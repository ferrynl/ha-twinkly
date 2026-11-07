import asyncio
import colorsys
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
from xled import HighControlInterface

DATA = Path("/data/devices.json")
PIXELS = 120
FRAME_BYTES = PIXELS * 3
MAX_DEVICES = 40
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
            self.size = 0


class Device:
    def __init__(self, row, limit):
        self.row = row
        self.limit = limit
        self.lock = asyncio.Lock()
        self.client = self.connect()
        self.restore = None
        self.last_mode = None
        self.effects = []
        self.effects_until = 0.0
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
        response = session.get(path) if payload is None else session.post(path, json=payload)
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 1000:
            raise ApplicationError(f"{path}: Twinkly code {data.get('code')}", response=response)
        return data

    def color(self, rgb):
        hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
        self.api("led/color", {"hue": round(hue * 360) % 360,
                               "saturation": round(saturation * 255), "value": round(value * 255)})
        self.client.set_mode("color").raise_for_status()

    def turn_on(self):
        for mode in dict.fromkeys((self.last_mode, "color", "demo", "effect", "playlist", "movie")):
            if mode is None:
                continue
            try:
                if mode == "color" and self.last_mode is None:
                    self.color((255, 190, 110))
                    self.last_mode = mode
                    return
                if self.client.set_mode(mode).ok:
                    self.last_mode = mode
                    return
            except (ApplicationError, HTTPError):
                continue
        self.color((255, 190, 110))
        self.last_mode = "color"

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
                self.client.set_mode(self.restore).raise_for_status()
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
            self.client.turn_off().raise_for_status()
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
            self.client.set_mode(kind).raise_for_status()
            self.last_mode = kind
        elif action == "brightness":
            self.client.set_brightness(value).raise_for_status()

    def send(self, frame):
        now = time.monotonic()
        if now >= self.rt_check:
            response = self.client.get_mode()
            response.raise_for_status()
            mode = response["mode"]
            if self.restore is None:
                self.restore = mode if mode != "rt" else "off"
            if mode != "rt":
                self.client.set_mode("rt").raise_for_status()
            self.rt_check = now + 2
        # RGBW controllers use white first on the realtime wire.
        white = b"\0" if self.row["profile"] == "RGBW" else b""
        payload = b"".join(white + frame[i:i + 3] for i in self.mapping)
        self.client.set_rt_frame_socket(io.BytesIO(payload), self.row["protocol"], self.row["leds"])

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
        self.devices = {}
        self.music = set()
        self.edit = asyncio.Lock()
        self.music_setup = asyncio.Lock()
        self.probe = asyncio.Semaphore(6)
        if DATA.exists():
            for row in json.loads(DATA.read_text()):
                self.devices[row["id"]] = Device(row, self.limit)

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
                    "leds": leds, "profile": profile,
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
            self.devices[key] = Device(row, self.limit)
            self.save()
        return row

    def save(self):
        temp = DATA.with_suffix(".tmp")
        temp.write_text(json.dumps([d.row for d in self.devices.values()]), encoding="utf-8")
        temp.replace(DATA)

    async def output(self, device):
        key = device.row["id"]
        while self.devices.get(key) is device:
            now = time.monotonic()
            active = key in self.music and self.ddp.frame is not None and now - self.ddp.received < 1.5
            if now >= device.retry:
                if active:
                    await device.run(device.send, self.ddp.frame)
                elif device.restore is not None:
                    await device.run(device.command, "stop", None)
                    device.rt_check = 0
            await asyncio.sleep(1 / self.fps if active else 0.2)

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

    async def status(self, request):
        return web.json_response({
            "audio": self.ddp.frame is not None and time.monotonic() - self.ddp.received < 1.5,
            "devices": [dict(d.row, music=k in self.music, error=d.error)
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

    async def effects(self, request):
        device = self.devices.get(request.query.get("id"))
        if device is None:
            raise web.HTTPNotFound()
        ok = await device.run(device.load_effects)
        return web.json_response({"effects": device.effects, "error": None if ok else device.error})

    async def setup_music(self, request):
        if self.source != "127.0.0.1":
            return web.json_response({"message": "Automatische koppeling vereist LedFX op dezelfde Home Assistant-host en ddp_source 127.0.0.1."})
        async with self.music_setup:
            try:
                async with ClientSession(base_url="http://127.0.0.1:8888", timeout=ClientTimeout(total=10)) as session:
                    await configure_ledfx(session)
            except (ClientError, TimeoutError, ValueError, KeyError) as exc:
                LOG.warning("LedFX setup: %s", exc)
                return web.json_response({"message": f"LedFX koppelen mislukt: {exc or type(exc).__name__}"})
        return web.json_response({
            "ok": True,
            "message": "LedFX ingesteld. Voeg LedFx Twinkly toe aan de afspeelgroep in Music Assistant en start muziek."
        })

    def app(self):
        self.edit_scan = asyncio.Lock()
        app = web.Application(middlewares=[ingress_only], client_max_size=8192)
        app.cleanup_ctx.append(self.stream)
        app.router.add_get("/", lambda _: web.FileResponse("index.html"))
        app.router.add_get("/status", self.status)
        app.router.add_get("/effects", self.effects)
        app.router.add_post("/register", self.register)
        app.router.add_post("/control", self.control)
        app.router.add_post("/setup-music", self.setup_music)
        return app


async def configure_ledfx(session):
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
    if not (await api("GET", path)).get("effect"):
        await api("POST", path, {"type": "energy", "config": {}})


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
