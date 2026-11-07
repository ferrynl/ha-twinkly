import asyncio
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

from aiohttp import web
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


def discover():
    found = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(b"\x01discover", ("255.255.255.255", 5555))
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
        self.rt_check = 0.0
        self.retry = 0.0
        self.error = None
        self.mapping = tuple(3 * (i * PIXELS // row["leds"]) for i in range(row["leds"]))

    def connect(self):
        client = HighControlInterface(self.row["ip"])
        client.session.trust_env = False
        client.session.request = functools.partial(client.session.request, timeout=(1, 2))
        return client

    def command(self, action, value):
        if action == "stop":
            if self.restore is not None:
                self.client.set_mode(self.restore)
                self.restore = None
            return
        if action == "music":
            return
        self.command("stop", None)
        if action == "on":
            self.client.turn_on()
        elif action == "off":
            self.client.turn_off()
        elif action == "color":
            self.client.set_led_color_rgb(*value)
            self.client.set_mode("color")
        elif action == "brightness":
            self.client.set_brightness(value)

    def send(self, frame):
        now = time.monotonic()
        if now >= self.rt_check:
            mode = self.client.get_mode()["mode"]
            if self.restore is None:
                self.restore = mode if mode != "rt" else "off"
            if mode != "rt":
                self.client.set_mode("rt")
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
                self.error = type(exc).__name__
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
        self.limit = asyncio.Semaphore(8)
        self.devices = {}
        self.music = set()
        self.edit = asyncio.Lock()
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
            hosts = [data["ip"]] if data.get("ip") else await asyncio.to_thread(discover)
            results = await asyncio.gather(*(self.add(host) for host in hosts), return_exceptions=True)
        return web.json_response({"added": sum(isinstance(x, dict) for x in results),
                                  "errors": [f"{host}: {result}" for host, result in zip(hosts, results)
                                             if isinstance(result, Exception)]})

    async def control(self, request):
        data = await request.json()
        action = data.get("action")
        value = data.get("value")
        if action not in ("on", "off", "color", "brightness", "music", "stop"):
            raise web.HTTPBadRequest()
        if action == "color":
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise web.HTTPBadRequest()
            value = bytes.fromhex(value[1:])
        if action == "brightness" and (type(value) is not int or not 0 <= value <= 100):
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
        return web.json_response({"failed": [key for key, ok in zip(keys, results) if not ok]})

    def app(self):
        self.edit_scan = asyncio.Lock()
        app = web.Application(middlewares=[ingress_only], client_max_size=8192)
        app.cleanup_ctx.append(self.stream)
        app.router.add_get("/", lambda _: web.FileResponse("index.html"))
        app.router.add_get("/status", self.status)
        app.router.add_post("/register", self.register)
        app.router.add_post("/control", self.control)
        return app


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
