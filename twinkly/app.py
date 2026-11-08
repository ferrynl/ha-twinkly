import asyncio
import base64
import bisect
import hashlib
import uuid
import xml.etree.ElementTree as ET
import colorsys
import math
import os
from urllib.parse import urlsplit
from requests.exceptions import HTTPError, RequestException, Timeout
from xled.exceptions import ApplicationError
import fcntl
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

from aiohttp import ClientConnectorError, ClientError, ClientSession, ClientTimeout, web
from PIL import Image
from xled import HighControlInterface

DATA = Path("/data/devices.json")
GROUPS = DATA.with_name("groups.json")
MUSIC_STATE = DATA.with_name("music-state.json")
SHOW_STATE = DATA.with_name("show-state.json")
SEQUENCES = DATA.with_name("sequences.json")
TV_STATE = DATA.with_name("tv-state.json")
SILENCE_MODES = ("restore", "warm", "fade")
IMAGES = DATA.with_name("effect-images")
GIF_LIBRARY = DATA.with_name("gif-library")
MATRIX_GIFS = Path(__file__).resolve().with_name("matrix_gifs")
MATRIX_ID = re.compile(r"(?:winter|festive|neon|ocean|gold|cosmic|tropical|retro|pastel|midnight)-(?:[1-9]|10)")
GIF_LIMIT = 512 * 1024
GIF_ID = re.compile(r"[a-f0-9]{12}-[a-zA-Z0-9_-]{1,48}")
PRODUCT_PHOTOS = DATA.with_name("product-photos")
WORDMARK = DATA.with_name("twinkly-wordmark.svg")
WORDMARK_URL = "https://twinkly.com/cdn/shop/files/Twinkly_Logo_White.svg"
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
        targets = {broadcast}
        for _, name in socket.if_nameindex():
            interface = struct.pack("256s", name.encode())
            try:
                flags = struct.unpack_from("H", fcntl.ioctl(sock, 0x8913, interface), 16)[0]  # SIOCGIFFLAGS
                if flags & 0x3 != 0x3:  # IFF_UP and IFF_BROADCAST
                    continue
                address = fcntl.ioctl(sock, 0x8919, interface)  # SIOCGIFBRDADDR
                targets.add(socket.inet_ntoa(address[20:24]))
            except OSError:
                continue
        for target in sorted(targets):
            try:
                sock.sendto(b"\x01discover", (target, 5555))
            except OSError as exc:
                LOG.debug("Twinkly broadcast naar %s mislukt: %s", target, exc)
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


PATTERN_PALETTES = {
    "rainbow": (), "aurora": ((4, 25, 68), (29, 230, 137), (129, 47, 229)),
    "fire": ((43, 3, 0), (255, 53, 0), (255, 194, 47)),
    "ice": ((10, 24, 60), (30, 129, 255), (165, 242, 255)),
    "ocean": ((3, 13, 52), (0, 95, 175), (26, 222, 194)),
    "candy": ((222, 16, 35), (255, 238, 210)),
    "sunset": ((95, 16, 102), (234, 43, 110), (255, 168, 48)),
    "sparkle": (),
}


PATTERN_PRESETS = {
    "winter-1": (0, 0, ((16, 56, 41), (55, 166, 122), (222, 247, 238))),
    "winter-2": (0, 1, ((21, 63, 39), (184, 29, 56), (255, 178, 93))),
    "winter-3": (0, 2, ((8, 14, 60), (66, 90, 169), (243, 217, 160))),
    "winter-4": (0, 3, ((81, 36, 25), (199, 96, 50), (255, 225, 174))),
    "winter-5": (0, 4, ((20, 32, 54), (148, 192, 221), (239, 252, 255))),
    "winter-6": (0, 5, ((212, 21, 56), (255, 244, 222), (149, 22, 43))),
    "winter-7": (0, 6, ((46, 9, 8), (199, 65, 45), (255, 175, 77))),
    "winter-8": (0, 7, ((9, 45, 30), (40, 136, 76), (211, 220, 120))),
    "winter-9": (0, 8, ((50, 16, 65), (164, 73, 142), (255, 173, 207))),
    "winter-10": (0, 9, ((52, 26, 10), (178, 123, 46), (255, 223, 144))),
    "lounge-1": (1, 0, ((32, 18, 32), (189, 101, 45), (255, 215, 145))),
    "lounge-2": (1, 1, ((55, 27, 64), (207, 105, 148), (255, 219, 206))),
    "lounge-3": (1, 2, ((24, 8, 45), (79, 43, 136), (199, 101, 181))),
    "lounge-4": (1, 3, ((42, 16, 0), (153, 96, 33), (255, 215, 138))),
    "lounge-5": (1, 4, ((9, 13, 36), (56, 81, 124), (166, 202, 224))),
    "lounge-6": (1, 5, ((33, 18, 13), (145, 87, 52), (239, 187, 121))),
    "lounge-7": (1, 6, ((68, 28, 38), (187, 77, 56), (248, 187, 130))),
    "lounge-8": (1, 7, ((33, 28, 74), (114, 100, 176), (228, 202, 255))),
    "lounge-9": (1, 8, ((14, 46, 38), (75, 146, 118), (179, 223, 172))),
    "lounge-10": (1, 9, ((70, 29, 51), (201, 100, 98), (255, 218, 177))),
    "nature-1": (2, 0, ((6, 21, 51), (8, 124, 147), (64, 241, 194))),
    "nature-2": (2, 1, ((6, 40, 36), (38, 123, 62), (182, 239, 99))),
    "nature-3": (2, 2, ((37, 5, 9), (172, 37, 8), (255, 152, 51))),
    "nature-4": (2, 3, ((17, 26, 82), (38, 125, 228), (202, 248, 255))),
    "nature-5": (2, 4, ((54, 18, 74), (240, 77, 114), (255, 191, 134))),
    "nature-6": (2, 5, ((68, 35, 49), (179, 101, 64), (255, 214, 138))),
    "nature-7": (2, 6, ((23, 57, 54), (115, 181, 72), (255, 232, 118))),
    "nature-8": (2, 7, ((5, 29, 67), (0, 122, 158), (116, 245, 241))),
    "nature-9": (2, 8, ((58, 24, 32), (184, 61, 38), (241, 183, 83))),
    "nature-10": (2, 9, ((19, 13, 73), (21, 202, 147), (179, 104, 231))),
    "neon-1": (3, 0, ((5, 39, 16), (97, 255, 36), (204, 255, 121))),
    "neon-2": (3, 1, ((50, 4, 46), (252, 26, 194), (255, 165, 239))),
    "neon-3": (3, 2, ((8, 13, 70), (22, 112, 255), (118, 250, 255))),
    "neon-4": (3, 3, ((68, 12, 58), (255, 50, 99), (255, 179, 34))),
    "neon-5": (3, 4, ((18, 41, 33), (115, 255, 112), (255, 252, 69))),
    "neon-6": (3, 5, ((33, 13, 85), (117, 45, 255), (219, 119, 255))),
    "neon-7": (3, 6, ((21, 23, 65), (255, 50, 106), (36, 244, 226))),
    "neon-8": (3, 7, ((4, 53, 46), (25, 255, 189), (173, 255, 239))),
    "neon-9": (3, 8, ((48, 16, 64), (206, 34, 255), (255, 71, 108))),
    "neon-10": (3, 9, ((7, 22, 73), (43, 139, 255), (236, 255, 77))),
    "sparkle-1": (4, 0, ((41, 25, 7), (194, 148, 78), (255, 240, 173))),
    "sparkle-2": (4, 1, ((18, 27, 48), (134, 181, 208), (255, 255, 255))),
    "sparkle-3": (4, 2, ((16, 36, 24), (142, 167, 52), (255, 245, 141))),
    "sparkle-4": (4, 3, ((52, 6, 20), (201, 23, 69), (255, 157, 174))),
    "sparkle-5": (4, 4, ((8, 29, 74), (41, 107, 242), (138, 223, 255))),
    "sparkle-6": (4, 5, ((35, 18, 59), (147, 68, 199), (235, 181, 255))),
    "sparkle-7": (4, 6, ((9, 43, 37), (50, 202, 162), (181, 255, 230))),
    "sparkle-8": (4, 7, ((50, 21, 8), (188, 81, 43), (255, 187, 116))),
    "sparkle-9": (4, 8, ((36, 32, 50), (169, 146, 174), (255, 241, 230))),
    "sparkle-10": (4, 9, ((19, 20, 46), (83, 96, 207), (255, 180, 224))),
}
PATTERN_PALETTES.update({name: preset[2] for name, preset in PATTERN_PRESETS.items()})


@functools.lru_cache(maxsize=64)
def live_pattern(name, tick, fps):
    time_seconds = tick / fps
    frame = bytearray()
    preset = PATTERN_PRESETS.get(name)
    for index in range(PIXELS):
        position = index / PIXELS
        if preset:
            family, variant, palette = preset
            phase = time_seconds * (0.08 + variant * 0.017)
            if family == 0:
                wave = (position * (3 + variant % 4) - phase) % 1
                rgb = palette[int(wave * len(palette))]
            elif family == 4:
                peak = (0.5 + 0.5 * math.cos((index * 0.618 + phase * 2) * math.tau)) ** 11
                rgb = tuple(round(a + (b-a)*peak) for a,b in zip(palette[0], palette[2]))
            else:
                wave = position * (1 + variant % 3) - phase
                if family == 2:
                    wave += 0.21 * math.sin(position * 14 + phase * math.tau)
                elif family == 3:
                    wave *= 3
                weight = (0.5 + 0.5 * math.sin(wave * math.tau))
                if family == 3:
                    weight **= 3
                scaled = weight * (len(palette) - 1)
                first = min(len(palette) - 2, int(scaled))
                fraction = scaled - first
                rgb = tuple(round(a + (b-a)*fraction) for a,b in zip(palette[first], palette[first+1]))
        elif name == "rainbow":
            rgb = tuple(round(channel * 255) for channel in colorsys.hsv_to_rgb(
                (position - time_seconds * 0.16) % 1, 0.92, 0.95))
        elif name == "sparkle":
            phase = (time_seconds * (0.7 + index % 7 * 0.09) + index * 0.618) % 1
            glow = 0.12 + 0.88 * (0.5 + 0.5 * math.cos(phase * math.tau)) ** 9
            rgb = tuple(round(channel * glow) for channel in (255, 192, 104))
        else:
            palette = PATTERN_PALETTES[name]
            wave = position * (6 if name == "candy" else 2) - time_seconds * 0.27
            if name != "candy":
                wave += 0.22 * math.sin(position * 13 + time_seconds * 1.1)
            scaled = (wave % 1) * len(palette)
            first = int(scaled)
            fraction = scaled - first
            if name == "candy":
                fraction = min(1, max(0, (fraction - 0.8) * 5))
            rgb = tuple(round(a + (b-a) * fraction) for a, b in
                        zip(palette[first], palette[(first+1) % len(palette)]))
        frame.extend(rgb)
    return bytes(frame)


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
        self.failures = 0
        self.last_warning = None
        self.last_warning_at = 0.0
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
            if payload is None:
                response = session.get(path, withhold_token=path in ("gestalt", "fw/version"))
                if response.status_code == 401 and path in ("gestalt", "fw/version"):
                    response = session.get(path)
            else:
                response = session.post(path, json=payload)
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
            except HTTPError as exc:
                if exc.response.status_code == 401:
                    raise
            except ApplicationError:
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
                now = time.monotonic()
                operation = method.__name__
                if operation == "command" and args:
                    operation = str(args[0])
                status = exc.response.status_code if isinstance(exc, HTTPError) and exc.response is not None else None
                if status == 401:
                    message = "HTTP 401: lamp weigerde het vernieuwde toegangstoken"
                elif isinstance(exc, Timeout):
                    message = f"Verbinding liep vast (timeout): {exc}"
                else:
                    message = str(exc) or type(exc).__name__
                self.error = message
                self.failures += 1
                delay = min(60, 5 * 2 ** min(self.failures - 1, 4))
                self.retry = now + delay
                self.rt_check = 0
                if isinstance(exc, RequestException) and (status is None or status == 401):
                    self.client.session.close()
                    self.client = self.connect()
                warning = (operation, type(exc), status)
                if warning != self.last_warning or now - self.last_warning_at >= 60:
                    LOG.warning("lamp=%r ip=%s actie=%s: %s", self.row["name"], self.row["ip"], operation, message)
                    self.last_warning, self.last_warning_at = warning, now
                return False
            self.error = None
            self.retry = 0
            self.failures = 0
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
        self.patterns = {}
        self.sequence_data = (json.loads(SEQUENCES.read_text(encoding="utf-8"))
                              if SEQUENCES.exists() else {"shows": {}, "favorites": []})
        self.sequence_task = None
        self.sequence_stop = asyncio.Event()
        self.sequence_lock = asyncio.Lock()
        self.sequence_status = None
        self.sequence_devices = {}
        self.sequence_error = None
        self.gif_patterns = {}
        self.gif_library_lock = asyncio.Lock()
        self.edit = asyncio.Lock()
        self.music_setup = asyncio.Lock()
        self.active_style = (json.loads(MUSIC_STATE.read_text(encoding='utf-8')).get('style')
                             if MUSIC_STATE.is_file() else None)
        self.gif_capture = asyncio.Lock()
        self.photo_lock = asyncio.Lock()
        self.track_lock = asyncio.Lock()
        self.media_player = (json.loads(TV_STATE.read_text(encoding='utf-8')).get('player', '')
                             if TV_STATE.exists() else options.get('media_player', '').strip())
        self.ha_media_until = 0.0
        self.ha_media_states = []
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
                self.patterns.pop(key, None)
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
            pattern = self.patterns.get(key)
            armed = key in self.music
            active = (armed and self.ddp.frame is not None and now - self.ddp.received < 1.5
                      and now - self.ddp.lit_at < 3)
            fading = False
            if now >= device.retry:
                if pattern:
                    if pattern.startswith(("gif:", "matrix:")):
                        timing, frames = self.gif_patterns[pattern]
                        index = bisect.bisect_right(timing, int(now * 1000) % timing[-1])
                        frame = frames[index]
                    else:
                        frame = live_pattern(pattern, int(now * self.fps), self.fps)
                    level = self.sequence_devices.get(key, 100)
                    await device.run(device.send, self.dim_frame(frame, level))
                elif active:
                    fade_started = None
                    frame = self.dim_frame(self.ddp.frame, self.show["master"] * self.sequence_devices.get(key, 100) // 100)
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
            await asyncio.sleep(1 / self.fps if pattern or active or fading else 0.2)

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
        self.sequence_stop.set()
        if self.sequence_task:
            await self.sequence_task
        transport.close()
        # Let outstanding device operations finish before restoring modes.
        self.music.clear()
        self.patterns.clear()
        await asyncio.gather(*(d.run(d.command, "stop", None) for d in self.devices.values()))
        for _, task in workers.values():
            task.cancel()
        await asyncio.gather(*(task for _, task in workers.values()), return_exceptions=True)
        self.realtime_socket.close()

    async def status(self, request):
        return web.json_response({
            "audio": self.ddp.frame is not None and time.monotonic() - self.ddp.received < 1.5,
            "groups": self.groups,
            "sequence": self.sequence_status,
            "sequence_error": self.sequence_error,
            "sequence_data": self.sequence_data,
            "active_music_style": self.active_style,
            "show": self.show,
            "devices": [dict(d.row, music=k in self.music, mode=d.mode, error=d.error, product_code=d.product_code, pattern=self.patterns.get(k))
                        for k, d in self.devices.items()],
        })

    async def register(self, request):
        data = await request.json()
        async with self.edit_scan:
            hosts = [data["ip"]] if data.get("ip") else await asyncio.to_thread(discover, self.broadcast)
            if not hosts:
                return web.json_response({"added": 0, "errors": [
                    "Geen Twinkly-antwoord op UDP-poort 5555. Controleer of de lampen op hetzelfde LAN zitten of voeg hun IP-adres toe."
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

    async def twinkly_wordmark(self, request):
        if not WORDMARK.is_file():
            async with self.photo_lock:
                if not WORDMARK.is_file():
                    try:
                        async with ClientSession(timeout=ClientTimeout(total=8)) as session:
                            async with session.get(WORDMARK_URL, allow_redirects=False) as response:
                                response.raise_for_status()
                                raw = bytearray()
                                async for chunk in response.content.iter_chunked(8192):
                                    raw.extend(chunk)
                                    if len(raw) > 256_000:
                                        raise ValueError("Twinkly SVG too large")
                        if b"<!DOCTYPE" in raw.upper() or ET.fromstring(raw).tag != "{http://www.w3.org/2000/svg}svg":
                            raise ValueError("Invalid Twinkly SVG")
                        temp = WORDMARK.with_suffix(".tmp")
                        temp.write_bytes(raw)
                        temp.replace(WORDMARK)
                    except (ClientError, TimeoutError, ValueError, OSError, ET.ParseError) as exc:
                        LOG.warning("Twinkly wordmark: %s", exc)
                        raise web.HTTPBadGateway() from exc
        return web.FileResponse(WORDMARK, headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "private, max-age=86400",
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        })

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

    @staticmethod
    def valid_pattern(value):
        return isinstance(value, str) and (
            value in PATTERN_PALETTES
            or (value.startswith("gif:") and GIF_ID.fullmatch(value[4:]))
            or (value.startswith("matrix:") and MATRIX_ID.fullmatch(value[7:]))
        )

    async def control(self, request):
        return web.json_response(await self.apply_control(await request.json()))

    async def apply_control(self, data, sequence_level=None):
        action = data.get("action")
        value = data.get("value")
        if action not in ("on", "off", "color", "brightness", "music", "stop", "effect", "pattern", "stop-pattern"):
            raise web.HTTPBadRequest()
        if action == "color":
            if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise web.HTTPBadRequest()
            value = bytes.fromhex(value[1:])
        if action == "brightness" and (type(value) is not int or not 0 <= value <= 100):
            raise web.HTTPBadRequest()
        if action == "pattern" and not self.valid_pattern(value):
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
            if action == "pattern":
                if value.startswith(("gif:", "matrix:")) and value not in self.gif_patterns:
                    kind, gif_id = value.split(":", 1)
                    root = MATRIX_GIFS if kind == "matrix" else GIF_LIBRARY
                    try:
                        self.gif_patterns[value] = await asyncio.to_thread(
                            self.decode_gif, (root / (gif_id + ".gif")).read_bytes(), kind == "matrix")
                    except (OSError, ValueError) as exc:
                        raise web.HTTPBadRequest(text="GIF unavailable") from exc
                self.music.difference_update(keys)
                self.patterns.update(dict.fromkeys(keys, value))
                self.mark_sequence_devices(keys, sequence_level)
                return {"failed": []}
            if action == "stop-pattern":
                keys = [key for key in keys if key in self.patterns]
                action = "stop"
            for key in keys:
                self.patterns.pop(key, None)
            self.mark_sequence_devices(keys, sequence_level if action == "music" else None)
            if action == "music":
                self.music.update(keys)
                return {"failed": []}
            self.music.difference_update(keys)
            results = await asyncio.gather(*(self.devices[k].run(self.devices[k].command, action, value)
                                             for k in keys))
            return {"failed": [
                f"{self.devices[key].row['ip']}: {self.devices[key].error}"
                for key, ok in zip(keys, results) if not ok
            ]}

    def mark_sequence_devices(self, keys, level):
        for key in keys:
            if level is None:
                self.sequence_devices.pop(key, None)
            else:
                self.sequence_devices[key] = level

    async def finish_sequence_step(self):
        async with self.edit:
            keys = list(self.sequence_devices)
            self.sequence_devices.clear()
            self.music.difference_update(keys)
            for key in keys:
                self.patterns.pop(key, None)
            await asyncio.gather(*(self.devices[key].run(self.devices[key].command, "stop", None)
                                   for key in keys if key in self.devices))

    async def play_sequence(self, key, show):
        try:
            for index, step in enumerate(show["steps"]):
                if self.sequence_stop.is_set():
                    break
                target = {"id": "*"} if step["group"] == "*" else {"group": step["group"]}
                command = {"action": "music"} if step["pattern"] == "music" else {
                    "action": "pattern", "value": step["pattern"]
                }
                await self.apply_control({**target, **command}, sequence_level=step["level"])
                self.sequence_status = {"id": key, "name": show["name"], "step": index + 1,
                                        "total": len(show["steps"]), "ends": time.time() + step["seconds"]}
                try:
                    await asyncio.wait_for(self.sequence_stop.wait(), step["seconds"])
                except TimeoutError:
                    pass
                finally:
                    await self.finish_sequence_step()
        except (web.HTTPException, OSError, ValueError) as exc:
            self.sequence_error = exc.text if isinstance(exc, web.HTTPException) else str(exc)
            LOG.warning("Show %r: %s", show["name"], self.sequence_error)
        finally:
            self.sequence_status = None

    async def sequences(self, request):
        data = await request.json()
        action, key = data.get("action"), data.get("id")
        async with self.sequence_lock:
            shows = self.sequence_data["shows"].copy()
            favorites = self.sequence_data["favorites"].copy()
            if action in ("play", "stop"):
                if action == "play" and (not isinstance(key, str) or key not in shows):
                    raise web.HTTPNotFound()
                if self.sequence_task and not self.sequence_task.done():
                    self.sequence_stop.set()
                    await self.sequence_task
                if action == "play":
                    self.sequence_stop.clear()
                    self.sequence_error = None
                    self.sequence_task = asyncio.create_task(self.play_sequence(key, shows[key]))
                return web.json_response({"ok": True})
            if action == "favorite":
                pattern = data.get("pattern")
                if not self.valid_pattern(pattern):
                    raise web.HTTPBadRequest()
                if pattern in favorites:
                    favorites.remove(pattern)
                elif len(favorites) < 8:
                    favorites.append(pattern)
                else:
                    raise web.HTTPConflict(text="Maximum 8 favorites")
            elif action == "delete":
                if not isinstance(key, str) or key not in shows:
                    raise web.HTTPNotFound()
                del shows[key]
            elif action == "save":
                name, steps = data.get("name"), data.get("steps")
                if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 60
                        or not isinstance(steps, list) or not 1 <= len(steps) <= 30):
                    raise web.HTTPBadRequest()
                if key is not None and (not isinstance(key, str) or key not in shows):
                    raise web.HTTPNotFound()
                if key is None and len(shows) >= 30:
                    raise web.HTTPConflict()
                validated = []
                for step in steps:
                    if not isinstance(step, dict):
                        raise web.HTTPBadRequest()
                    group, pattern = step.get("group"), step.get("pattern")
                    seconds, level = step.get("seconds"), step.get("level")
                    if (not isinstance(group, str) or (group != "*" and group not in self.groups)
                            or (pattern != "music" and not self.valid_pattern(pattern))
                            or type(seconds) is not int or not 1 <= seconds <= 3600
                            or type(level) is not int or not 0 <= level <= 100):
                        raise web.HTTPBadRequest()
                    validated.append({"group": group, "pattern": pattern, "seconds": seconds, "level": level})
                shows[key or uuid.uuid4().hex] = {"name": name.strip(), "steps": validated}
            else:
                raise web.HTTPBadRequest()
            updated = {"shows": shows, "favorites": favorites}
            temp = SEQUENCES.with_suffix(".tmp")
            temp.write_text(json.dumps(updated), encoding="utf-8")
            temp.replace(SEQUENCES)
            self.sequence_data = updated
        return web.json_response({"ok": True})

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

    @staticmethod
    def ha_headers():
        return {"Authorization": "Bearer " + os.environ["SUPERVISOR_TOKEN"]}

    async def media_players(self, request):
        try:
            async with ClientSession(timeout=ClientTimeout(total=4)) as session:
                async with session.get("http://supervisor/core/api/states",
                                       headers=self.ha_headers(), allow_redirects=False) as response:
                    response.raise_for_status()
                    states = await response.json()
        except (ClientError, TimeoutError, ValueError, KeyError) as exc:
            raise web.HTTPBadGateway() from exc
        players = []
        for state in states:
            entity = state.get("entity_id", "")
            if re.fullmatch(r"media_player\.[a-z0-9_]+", entity):
                attrs = state.get("attributes") or {}
                players.append({"id": entity, "name": attrs.get("friendly_name") or entity,
                                "state": state.get("state")})
        players.sort(key=lambda item: (item["state"] != "playing", item["name"].casefold(), item["id"]))
        return web.json_response({"players": players, "selected": self.media_player})

    async def select_media_player(self, request):
        data = await request.json()
        player = data.get("player")
        if not isinstance(player, str) or (player and not re.fullmatch(r"media_player\.[a-z0-9_]+", player)):
            raise web.HTTPBadRequest()
        async with self.track_lock:
            temp = TV_STATE.with_suffix(".tmp")
            temp.write_text(json.dumps({"player": player}), encoding="utf-8")
            temp.replace(TV_STATE)
            self.media_player = player
            self.ha_media_until = self.track_until = 0.0
            self.ha_media_states = []
        return web.json_response({"ok": True})

    async def home_assistant_media(self, now, track):
        if not self.media_player and not track:
            return None
        if now >= self.ha_media_until:
            self.ha_media_until = now + 12
            self.ha_media_states = []
            if self.media_player and not re.fullmatch(r"media_player\.[a-z0-9_]+", self.media_player):
                return None
            endpoint = "http://supervisor/core/api/states"
            if self.media_player:
                endpoint += "/" + self.media_player
            try:
                async with ClientSession(timeout=ClientTimeout(total=2)) as session:
                    async with session.get(endpoint, headers=self.ha_headers(),
                                           allow_redirects=False) as response:
                        response.raise_for_status()
                        data = await response.json()
                states = [data] if self.media_player else data
                self.ha_media_states = [item for item in states
                                        if item.get("entity_id", "").startswith("media_player.")]
            except (ClientError, TimeoutError, ValueError, KeyError):
                return None
        matches = []
        for item in self.ha_media_states:
            attrs = item.get("attributes") or {}
            title = str(attrs.get("media_title") or "").strip()
            if item.get("state") not in ("playing", "paused", "buffering") or not title:
                continue
            if self.media_player or title.casefold() == track["title"].strip().casefold():
                matches.append(attrs)
        return next((attrs for attrs in matches if attrs.get("entity_picture_local")
                     or attrs.get("entity_picture")), matches[0] if matches else None)

    @staticmethod
    def cover_url(value):
        if not isinstance(value, str) or len(value) > 4096:
            return None
        try:
            url = urlsplit(value)
        except ValueError:
            return None
        if (url.scheme == "https" and url.netloc == "i.ytimg.com"
                and re.fullmatch(r"/vi(?:_webp)?/[A-Za-z0-9_-]{11}/[A-Za-z0-9_-]+\.(jpg|webp)", url.path)):
            return "https://i.ytimg.com" + url.path
        return None

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
                        cover = self.cover_url(artwork.get("url")) or self.cover_url(metadata.get("artwork_url"))
                        if cover:
                            track["cover_url"] = cover
                        if (re.fullmatch(r"now_playing/now_playing\.(jpg|jpeg|png|webp|gif)", path)
                                and re.fullmatch(r"[a-fA-F0-9]{8,128}", digest)):
                            self.track_art = (digest, path, "ledfx")
                            track["artwork"] = digest
                        self.track_state["track"] = track
                except (ClientError, TimeoutError, ValueError):
                    self.track_until = now + 10
                track = self.track_state["track"]
                attrs = await self.home_assistant_media(now, track)
                if attrs:
                    if track is None or self.media_player:
                        previous = track or {}
                        track = {"title": str(attrs["media_title"])[:512],
                                 "artist": str(attrs.get("media_artist") or "")[:512],
                                 "album": str(attrs.get("media_album_name") or "")[:512]}
                        if previous.get("title", "").strip().casefold() == track["title"].strip().casefold():
                            track.update({key: previous[key] for key in ("artwork", "cover_url") if key in previous})
                    for value in (attrs.get("entity_picture_local"), attrs.get("entity_picture")):
                        if not isinstance(value, str):
                            continue
                        try:
                            picture = urlsplit(value)
                        except ValueError:
                            continue
                        if re.fullmatch(r"/api/media_player_proxy/media_player\.[a-z0-9_]+", picture.path):
                            path = picture.path + ("?" + picture.query if picture.query else "")
                            digest = hashlib.sha256((track["title"] + path).encode()).hexdigest()
                            self.track_art = (digest, path, "ha")
                            track["artwork"] = digest
                            break
                        cover = self.cover_url(value)
                        if cover:
                            track.pop("artwork", None)
                            track["cover_url"] = cover
                            break
                    self.track_state = {"track": track, "available": True}
            return web.json_response(dict(self.track_state, player=self.media_player),
                                     headers={"Cache-Control": "no-store"})

    async def now_playing_art(self, request):
        async with self.track_lock:
            if self.track_art is None or request.query.get("v") != self.track_art[0]:
                raise web.HTTPNotFound()
            if self.track_art_cache is None or self.track_art_cache[0] != self.track_art:
                try:
                    _, path, source = self.track_art
                    if source == "ha":
                        url = "http://supervisor/core" + path
                        options = {"headers": self.ha_headers()}
                    else:
                        url = "http://127.0.0.1:8888/api/assets/download"
                        options = {"params": {"path": path}}
                    async with ClientSession(timeout=ClientTimeout(total=3)) as session:
                        async with session.get(url, allow_redirects=False, **options) as response:
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

    @staticmethod
    def decode_gif(raw, matrix=False):
        if len(raw) > GIF_LIMIT:
            raise ValueError("GIF exceeds 512 KiB")
        frames, timing = [], []
        with Image.open(io.BytesIO(raw), formats=["GIF"]) as image:
            if image.width * image.height > 1_000_000:
                raise ValueError("GIF dimensions too large")
            total = 0
            for index in range(121):
                try:
                    image.seek(index)
                except EOFError:
                    break
                if index == 120:
                    raise ValueError("GIF exceeds 120 frames")
                total += min(5000, max(40, image.info.get("duration", 100)))
                timing.append(total)
                size = (12, 10) if matrix else (PIXELS, 1)
                sampler = Image.Resampling.NEAREST if matrix else Image.Resampling.BOX
                frames.append(image.convert("RGB").resize(size, sampler).tobytes())
        if not frames:
            raise ValueError("Empty GIF")
        return tuple(timing), tuple(frames)

    async def matrix_catalog(self, request):
        return web.FileResponse(MATRIX_GIFS / "catalog.json")

    async def matrix_gif(self, request):
        key = request.match_info["id"]
        if not MATRIX_ID.fullmatch(key):
            raise web.HTTPNotFound()
        return web.FileResponse(MATRIX_GIFS / (key + ".gif"), headers={
            "Content-Type": "image/gif", "X-Content-Type-Options": "nosniff",
        })

    async def list_gifs(self, request):
        entries = [{"id": path.stem, "name": path.stem.split("-", 1)[1].replace("_", " ")}
                   for path in sorted(GIF_LIBRARY.glob("*.gif")) if GIF_ID.fullmatch(path.stem)]
        return web.json_response({"gifs": entries}, headers={"Cache-Control": "no-store"})

    async def download_giphy(self, gif_id):
        if not isinstance(gif_id, str) or not re.fullmatch(r"[A-Za-z0-9]{3,40}", gif_id):
            raise ValueError("Invalid GIPHY ID")
        async with ClientSession(timeout=ClientTimeout(total=8)) as session:
            for rendition in ("200w.gif", "100w.gif", "giphy-preview.gif", "giphy.gif"):
                url = f"https://media1.giphy.com/media/{gif_id}/{rendition}"
                async with session.get(url, allow_redirects=False) as response:
                    if response.status != 200 or response.content_type != "image/gif":
                        continue
                    if response.content_length and response.content_length > GIF_LIMIT:
                        continue
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(32768):
                        raw.extend(chunk)
                        if len(raw) > GIF_LIMIT:
                            break
                    try:
                        decoded = await asyncio.to_thread(self.decode_gif, raw)
                    except (OSError, ValueError, Image.DecompressionBombError):
                        continue
                    return raw, decoded
        raise ValueError("GIPHY GIF unavailable or exceeds the library limits")

    async def save_gif(self, request):
        data = await request.json()
        if "delete" in data:
            gif_id = data["delete"]
            if not isinstance(gif_id, str) or not GIF_ID.fullmatch(gif_id):
                raise web.HTTPBadRequest()
            async with self.edit, self.gif_library_lock:
                if "gif:" + gif_id in self.patterns.values():
                    raise web.HTTPConflict(text="Stop the GIF before deleting it")
                (GIF_LIBRARY / (gif_id + ".gif")).unlink(missing_ok=True)
                self.gif_patterns.pop("gif:" + gif_id, None)
            return web.json_response({"ok": True})
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            raise web.HTTPBadRequest()
        slug = re.sub(r"[^a-zA-Z0-9-]+", "_", name).strip("_")[:48] or "GIF"
        pattern = data.get("pattern")
        try:
            if "giphy" in data:
                raw, decoded = await self.download_giphy(data["giphy"])
            else:
                if isinstance(pattern, str) and pattern in PATTERN_PALETTES:
                    frames = [live_pattern(pattern, index, 10) for index in range(30)]
                    raw = await asyncio.to_thread(self.encode_gif, frames)
                else:
                    raw = base64.b64decode(data.get("image", ""), validate=True)
                decoded = await asyncio.to_thread(self.decode_gif, raw)
        except (ClientError, TimeoutError, ValueError, OSError, TypeError, Image.DecompressionBombError) as exc:
            raise web.HTTPBadRequest(text="Invalid GIF, or limits exceeded") from exc
        gif_id = hashlib.sha256(raw).hexdigest()[:12] + "-" + slug
        async with self.gif_library_lock:
            GIF_LIBRARY.mkdir(exist_ok=True)
            path = GIF_LIBRARY / (gif_id + ".gif")
            if not path.is_file():
                if sum(1 for _ in GIF_LIBRARY.glob("*.gif")) >= 30:
                    raise web.HTTPConflict(text="GIF library is full")
                temp = path.with_suffix(".tmp")
                temp.write_bytes(raw)
                temp.replace(path)
            self.gif_patterns["gif:" + gif_id] = decoded
        return web.json_response({"id": gif_id})

    async def gif_file(self, request):
        gif_id = request.match_info["id"]
        if not GIF_ID.fullmatch(gif_id):
            raise web.HTTPNotFound()
        path = GIF_LIBRARY / (gif_id + ".gif")
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Content-Type": "image/gif", "X-Content-Type-Options": "nosniff"})

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

    async def ledfx_status(self, request):
        async with ClientSession(base_url=LEDFX_URL, timeout=ClientTimeout(total=3)) as session:
            return web.json_response(await check_ledfx(session))

    async def setup_music(self, request):
        data = await request.json()
        style = data.get("style") if isinstance(data, dict) else None
        if style is not None and (not isinstance(style, str) or style not in MUSIC_STYLES):
            raise web.HTTPBadRequest()
        if self.source != "127.0.0.1":
            return web.json_response({"message": "Automatische koppeling vereist LedFX op dezelfde Home Assistant-host en ddp_source 127.0.0.1."})
        async with self.music_setup:
            try:
                async with ClientSession(base_url=LEDFX_URL, timeout=ClientTimeout(total=10)) as session:
                    check = await check_ledfx(session)
                    if not check["ok"]:
                        return web.json_response(check)
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
        app = web.Application(middlewares=[ingress_only], client_max_size=720_000)
        app.cleanup_ctx.append(self.stream)
        app.router.add_get("/", lambda _: web.FileResponse("index.html"))
        app.router.add_get("/twinkly.svg", lambda _: web.FileResponse("twinkly.svg"))
        app.router.add_get("/twinkly-wordmark.svg", self.twinkly_wordmark)
        app.router.add_get("/status", self.status)
        app.router.add_get("/effects", self.effects)
        app.router.add_get("/layout", self.layout)
        app.router.add_get("/details", self.details)
        app.router.add_post("/register", self.register)
        app.router.add_post("/control", self.control)
        app.router.add_post("/sequences", self.sequences)
        app.router.add_post("/groups", self.save_group)
        app.router.add_post("/show", self.save_show)
        app.router.add_get("/product-photo/{key}", self.product_photo)
        app.router.add_get("/effect-image", self.effect_image)
        app.router.add_post("/effect-image", self.effect_image)
        app.router.add_get("/ledfx-status", self.ledfx_status)
        app.router.add_post("/setup-music", self.setup_music)
        app.router.add_get("/music-preview", self.music_preview)
        app.router.add_get("/now-playing", self.now_playing)
        app.router.add_get("/media-players", self.media_players)
        app.router.add_post("/media-players", self.select_media_player)
        app.router.add_get("/now-playing-art", self.now_playing_art)
        app.router.add_post("/music-gif", self.music_gif)
        app.router.add_get("/matrix-gifs", self.matrix_catalog)
        app.router.add_get("/matrix-gifs/{id}", self.matrix_gif)
        app.router.add_get("/gifs", self.list_gifs)
        app.router.add_post("/gifs", self.save_gif)
        app.router.add_get("/gifs/{id}", self.gif_file)
        return app


LEDFX_URL = "http://127.0.0.1:8888"


async def check_ledfx(session):
    try:
        async with session.get("/api/info", allow_redirects=False) as response:
            info = await response.json() if response.status == 200 else None
    except (ClientConnectorError, TimeoutError):
        return {"ok": False, "message": "LedFX is onbereikbaar op 127.0.0.1:8888. Installeer of start de LedFX-app en controleer de logs."}
    except (ClientError, ValueError):
        info = None
    if not isinstance(info, dict) or not isinstance(info.get("features"), dict):
        return {"ok": False, "message": "Poort 8888 reageert, maar geeft geen herkenbare LedFX-informatie. Controleer de app en poort."}
    if not info["features"].get("sendspin"):
        return {"ok": False, "message": "LedFX draait. Installeer of update naar een LedFX-versie met Sendspin-ondersteuning."}
    return {"ok": True, "message": "LedFX draait en ondersteunt Sendspin. Je kunt Music Assistant koppelen."}


async def configure_ledfx(session, style=None):
    async def api(method, path, body=None):
        async with session.request(method, "/api" + path, json=body, allow_redirects=False) as response:
            data = await response.json()
            if response.status >= 300 or data.get("status") in ("failed", "error"):
                reason = data.get("payload", {}).get("reason", f"HTTP {response.status}")
                raise ValueError(f"{path}: {reason}")
            return data

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

    config = {"name": "Twinkly Control Center", "ip_address": "127.0.0.1", "port": 18490,
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
    logging.Formatter.converter = time.gmtime
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)sZ %(levelname)s %(name)s: %(message)s",
                        datefmt="%Y-%m-%dT%H:%M:%S")
    # XLED retries 401s itself. Device.run reports the final failure with context.
    logging.getLogger("xled.auth").addFilter(
        lambda record: not record.getMessage().startswith("Unexpected HTTP status code 401 to request ")
    )
    options = json.loads(Path("/data/options.json").read_text())
    web.run_app(Controller(options).app(), host="0.0.0.0", port=18489, access_log=None)
