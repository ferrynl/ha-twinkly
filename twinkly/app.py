import asyncio
from collections import Counter
import base64
import bisect
import hashlib
import uuid
import tempfile
import colorsys
import math
import os
from urllib.parse import urlsplit
from requests.exceptions import ConnectionError as LampConnectionError
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
from PIL import Image, ImageDraw
from xled import HighControlInterface

HTTP_PORT = int(os.environ.get("TWINKLY_HTTP_PORT", "18489"))
DDP_PORT = int(os.environ.get("TWINKLY_DDP_PORT", "18490"))

DATA = Path("/data/devices.json")
GROUPS = DATA.with_name("groups.json")
MUSIC_STATE = DATA.with_name("music-state.json")
SHOW_STATE = DATA.with_name("show-state.json")
SEQUENCES = DATA.with_name("sequences.json")
TV_STATE = DATA.with_name("tv-state.json")
SILENCE_MODES = ("restore", "warm", "fade")
IMAGES = DATA.with_name("effect-images")
EFFECT_PREVIEWS = Path(__file__).resolve().with_name("effect_previews")
BUNDLED_EFFECT_PREVIEWS = {
    "24k future": "24k-future.gif",
    "cotton candy": "cotton-candy.gif",
    "flare": "flare.gif",
    "paradise": "paradise.gif",
    "peachy": "peachy.gif",
    "rainbow": "rainbow.gif",
    "solar sparks": "solar-sparks.gif",
}
GIF_LIBRARY = DATA.with_name("gif-library")
MATRIX_GIFS = Path(__file__).resolve().with_name("matrix_gifs")
MATRIX_ID = re.compile(r"(?:winter|festive|neon|ocean|gold|cosmic|tropical|retro|pastel|midnight)-(?:[1-9]|10)")
GIF_LIMIT = 512 * 1024
GIF_ID = re.compile(r"[a-f0-9]{12}-[a-zA-Z0-9_-]{1,48}")
PRODUCT_PHOTOS = Path(__file__).resolve().with_name("product_photos")
WORDMARK = Path(__file__).resolve().with_name("twinkly-nav-logo.svg")
PRODUCT_PHOTO_KEYS = frozenset({
    "c9-bulbs",
    "cluster-gold-silver",
    "cluster-multicolor",
    "cluster-multicolor-white",
    "curtain",
    "curtain-rgbw",
    "dots",
    "festoon-gold-silver",
    "festoon-multicolor",
    "flex",
    "icicle-gold-silver",
    "icicle-multicolor",
    "icicle-multicolor-white",
    "light-tree",
    "light-tree-2d",
    "lightwall",
    "line",
    "matrix",
    "net-lights",
    "permanent-lights",
    "pre-lit-garland",
    "pre-lit-tree",
    "pre-lit-wreath",
    "reindeers",
    "spheres",
    "spritzer",
    "squares",
    "strings-gold-silver",
    "strings-hd",
    "strings-multicolor",
    "strings-rgbw",
    "strings-usb-c-candles",
    "strings-usb-c-hearts",
    "strings-usb-c-pearls",
    "strings-usb-c-stars",
    "tree-topper",
})
PIXELS = 120
FRAME_BYTES = PIXELS * 3
MAX_DEVICES = 80
MAX_SAVED_GROUPS = 40
MAX_SAVED_SCENES = 40
MUSIC_STYLES = frozenset(('energy', 'spectrum', 'power', 'wavelength', 'strobe', 'scroll', 'bands', 'blade_power_plus', 'magnitude', 'fire', 'rain', 'melt', 'melt_and_sparkle', 'scan', 'water', 'energy2', 'bar', 'blocks', 'equalizer', 'lava_lamp', 'pitchSpectrum', 'scan_multi', 'scan_and_flare', 'scroll_plus', 'vumeter', 'multiBar'))
LOG = logging.getLogger("twinkly")


def asset_path(directory, filename):
    """Accept only a direct child of the configured asset directory."""
    if filename in ("", ".", "..") or Path(filename).name != filename:
        raise web.HTTPNotFound()
    path = directory / filename
    if directory.is_symlink() or path.is_symlink():
        raise web.HTTPNotFound()
    return path


def gif_asset(directory, identifier, pattern):
    if not pattern.fullmatch(identifier):
        raise web.HTTPNotFound()
    return asset_path(directory, identifier + ".gif")


def write_asset(path, data):
    """Replace the asset atomically without writing through a temporary symlink."""
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data)
            stream.close()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


async def health(request):
    return web.Response(text="OK", headers={"Cache-Control": "no-store"})


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
    "rgb-test": ((255, 0, 0), (0, 255, 0), (0, 0, 255)),
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
    if name == "rgb-test":
        palette = PATTERN_PALETTES[name]
        return bytes(palette[(tick // (3 * fps)) % len(palette)]) * PIXELS
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
        self.last_color = None
        self.last_brightness = None
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
        self.offline = False
        self.wifi_observation = None
        self.network_details = {}
        self.native_group = None
        self.native_layout_id = ""
        self.native_standalone = False
        self.native_identity = dict(row.get("native_identity", {}))
        self.native_group_until = 0
        self.removed = False
        self.replies = 0
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
        self.replies += 1
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
        self.remember_native_identity(info)
        self.product_code = info.get("product_code")
        self.model_checked = True

    def load_details(self):
        if time.monotonic() < self.details_until:
            return
        info = self.api("gestalt")
        self.remember_native_identity(info)
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
                details["ap_ssid"] = access_point.get("ssid")
                details["ap_ip"] = access_point.get("ip")
                details["bssid"] = station.get("bssid")
                details["rssi"] = station.get("rssi", data.get("rssi", details.get("rssi")))
                channel = station.get("channel") or data.get("channel")
                if channel is None and data.get("mode") in (0, 2):
                    channel = access_point.get("channel")
                details["channel"] = channel
        self.details = {key: value for key, value in details.items()
                        if isinstance(value, (str, int, float, bool)) and value != ""}
        self.load_native_group()
        self.details_until = time.monotonic() + 60

    def remember_native_identity(self, info):
        self.native_identity.update({field: info[field] for field in ("uuid", "mac", "hw_id")
                                     if isinstance(info.get(field), str) and info[field].strip()})

    def load_native_group(self):
        if time.monotonic() < self.native_group_until:
            return
        self.native_group_until = time.monotonic() + 60
        reported = None
        received = False
        for path, field in (("summary", "group"), ("led/movie/config", "sync")):
            try:
                payload = self.api(path)
            except (ApplicationError, ValueError, RequestException):
                continue
            if path == "summary":
                layout = payload.get("layout")
                layout_id = layout.get("uuid") if isinstance(layout, dict) else None
                self.native_layout_id = layout_id.strip().casefold() if isinstance(layout_id, str) else ""
            group = payload.get(field)
            if path == "summary":
                self.native_standalone = isinstance(group, dict) and group.get("mode") == "none"
            if not isinstance(group, dict):
                continue
            received = True
            role = group.get("mode")
            if role not in ("master", "slave"):
                continue
            uid = group.get("uid")
            uid = uid.strip() if isinstance(uid, str) else ""
            master = group.get("master_id")
            master = master.strip() if isinstance(master, str) else ""
            name = group.get("name")
            offset, size = group.get("offset"), group.get("size")
            entry = {
                "id": uid or master, "uid": bool(uid), "role": role,
                "master_id": master,
                "name": name.strip() if isinstance(name, str) else "",
                "offset": offset if type(offset) is int and offset >= 0 else None,
                "size": size if type(size) is int and size > 0 else None,
            }
            if reported is None:
                reported = entry
            elif reported["role"] == entry["role"]:
                if entry["uid"] and reported["uid"] and entry["id"] != reported["id"]:
                    LOG.warning("lamp=%r reports conflicting native group UIDs", self.row["name"])
                    continue
                for field in ("offset", "size"):
                    if entry[field] is not None:
                        reported[field] = entry[field]
                for field in ("id", "name", "master_id"):
                    if not reported[field] and entry[field]:
                        reported[field] = entry[field]
                if entry["master_id"] and entry["master_id"].casefold() != reported["master_id"].casefold():
                    reported["master_id"] = ""
                if entry["uid"] and not reported["uid"]:
                    reported["id"] = entry["id"]
                    reported["uid"] = True
        if received:
            if reported and reported["role"] == "master" and reported["offset"] is None:
                reported["offset"] = 0
            self.native_group = reported

    def load_layout(self):
        if time.monotonic() < self.layout_until:
            return
        data = self.api("led/layout/full")
        points = []
        for index, point in enumerate((data.get("coordinates") or [])[:65536]):
            if not isinstance(point, dict):
                continue
            coords = [point.get(axis, 0 if axis == "z" else None) for axis in ("x", "y", "z")]
            if all(type(value) in (int, float) and math.isfinite(value) for value in coords):
                points.append([index, *coords])
        layout_id = data.get("uuid")
        self.layout = {"points": points, "source": data.get("source"),
                       "uuid": layout_id.strip().casefold() if isinstance(layout_id, str) else "",
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
                catalog.extend({"kind": kind, "id": item["id"], "name": item.get("name", ""),
                                "unique_id": item.get("unique_id")}
                               for item in data.get("movies", []) if type(item.get("id")) is int)
            else:
                catalog.extend({"kind": kind, "id": index, "name": ""}
                               for index in range(min(256, int(data.get("effects_number", 0)))))
        identities = Counter(entry["unique_id"] for entry in catalog if isinstance(entry.get("unique_id"), str))
        for entry in catalog:
            unique_id = entry.get("unique_id")
            if (not isinstance(unique_id, str) or identities[unique_id] != 1
                    or unique_id in ("00000000-0000-0000-0000-000000000000", "00000000-0000-0000-8000-000000000000")):
                entry.pop("unique_id", None)
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
            self.last_color = list(value)
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
            response = self.client.set_brightness(value)
            self.replies += 1
            response.raise_for_status()
            self.last_brightness = value

    def send(self, frame, mapping=None):
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
        payload = b"".join(white + frame[i:i + 3] for i in (self.mapping if mapping is None else mapping))
        token = base64.b64decode(self.client.session.access_token)
        packets = realtime_packets(payload, token, self.row["protocol"], self.row["leds"])
        for packet in packets:
            self.realtime_socket.sendto(packet, (self.row["ip"], 7777))

    def mark_online(self):
        if self.offline:
            self.offline = False
            self.last_warning = None
            LOG.info("lamp=%r ip=%s status=online", self.row["name"], self.row["ip"])

    async def run(self, method, *args, automatic=False):
        async with self.lock, self.limit:
            if self.removed or (automatic and self.offline and time.monotonic() < self.retry):
                return False
            replies = self.replies
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
                offline = isinstance(exc, (LampConnectionError, Timeout)) or (
                    operation == "send" and isinstance(exc, OSError) and not isinstance(exc, RequestException)
                )
                newly_offline = offline and not self.offline
                if offline:
                    self.wifi_observation = None
                    self.network_details = {}
                    self.details_until = 0
                    self.offline = True
                    self.mode = None
                elif self.replies != replies or status is not None:
                    self.mark_online()
                self.error = "offline" if self.offline else "device_error"
                self.failures += 1
                delay = min(60, 5 * 2 ** min(self.failures - 1, 4))
                self.retry = now + delay
                self.rt_check = 0
                if isinstance(exc, RequestException) and (status is None or status == 401):
                    self.client.session.close()
                    self.client = self.connect()
                warning = (operation, type(exc), status)
                background_warning = (newly_offline or (not offline and (
                    warning != self.last_warning or now - self.last_warning_at >= 60)))
                if not automatic or background_warning:
                    LOG.warning("lamp=%r ip=%s actie=%s status=%s: %s",
                                self.row["name"], self.row["ip"], operation, self.error, message)
                    self.last_warning, self.last_warning_at = warning, now
                return False
            if self.replies != replies:
                self.mark_online()
            self.error = "offline" if self.offline else None
            self.retry = 0
            self.failures = 0
            return True


class Controller:
    def __init__(self, options):
        self.source = local_ip(options["ddp_source"])
        self.ddp = DDP(self.source)
        self.fps = options["fps"]
        self.govee_api_key = options.get("govee_api_key")
        self.broadcast = local_ip(options.get("discovery_broadcast", "255.255.255.255"))
        self.limit = asyncio.Semaphore(8)
        self.realtime_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.devices = {}
        self.show = (json.loads(SHOW_STATE.read_text(encoding="utf-8")) if SHOW_STATE.exists()
                     else {"master": 100, "scenes": {}})
        self.groups = json.loads(GROUPS.read_text(encoding='utf-8')) if GROUPS.exists() else {}
        self.native_group_names_path = DATA.with_name("native_group_names.json")
        self.native_group_names = (json.loads(self.native_group_names_path.read_text(encoding="utf-8"))
                                   if self.native_group_names_path.exists() else {})
        self.music = set()
        self.mixed_music_levels = {}
        self.patterns = {}
        self.group_routes = {}
        self.physical_tests = {}
        self.group_frames = {}
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
                    "native_identity": {field: info[field] for field in ("uuid", "mac", "hw_id")
                                        if isinstance(info.get(field), str) and info[field].strip()},
                    "name": str(info.get("device_name") or host), "ip": host,
                    "leds": leds, "profile": profile, "product_code": info.get("product_code"),
                    "protocol": 1 if str(info.get("product_version")) == "1" and leds <= 255 else 3}

    async def add(self, host):
        async with self.probe:
            row = await asyncio.to_thread(self.inspect, local_ip(host))
        async with self.edit:
            key = row["id"]
            old = self.devices.get(key)
            if old and "native_master_for" in old.row:
                row["native_master_for"] = old.row["native_master_for"]
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

    def save(self, *, exclude=None):
        temp = DATA.with_suffix(".tmp")
        temp.write_text(json.dumps([d.row for k, d in self.devices.items() if k != exclude]),
                        encoding="utf-8")
        temp.replace(DATA)

    @staticmethod
    def dim_frame(frame, level):
        return frame if level == 100 else bytes(channel * level // 100 for channel in frame)

    def silence_mode(self, key):
        # For overlapping groups, the first configured non-default rule wins.
        return next((group["silence"] for group in self.groups.values()
                     if key in group["members"] and group.get("silence", "restore") != "restore"), "restore")

    @staticmethod
    def mapped_points(device, count):
        layout = device.layout or {}
        points = {p[0]: p[1:] for p in layout.get("points", [])}
        if layout.get("synthesized") or set(points) != set(range(count)):
            raise ValueError("Complete physical LED mapping required")
        return points

    @staticmethod
    def transform_xy(x, y, settings):
        if settings.get("mirror_x"): x = 1-x
        if settings.get("mirror_y"): y = 1-y
        for _ in range(settings.get("rotation", 0)//90):
            x, y = 1-y, x
        return x, y

    def group_coordinates(self, key, members, mode, *, apply_reverse=True):
        device = self.devices[key]
        count = device.row["leds"]
        if mode == "join":
            entries = self.join_entries(members)
            leader, total = self.validate_join(entries)
            offset = entries[key]["offset"]
            points = self.join_points(entries, leader, total)
            selected = [points[offset+i] for i in range(count)]
        else:
            points = self.mapped_points(device, count)
            selected = [points[i] for i in range(count)]
        xs = [p[0] for p in points.values()]
        ys = [p[1] for p in points.values()]
        xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
        def normal(v, lo, hi):
            return (v-lo)/(hi-lo) if hi > lo else .5
        settings = device.row.get("mapping_override", {})
        if apply_reverse and settings.get("reverse"):
            selected.reverse()
        result = []
        for x, y, *_ in selected:
            x, y = normal(x, xmin, xmax), normal(y, ymin, ymax)
            x, y = self.transform_xy(x, y, settings)
            if mode == "area":
                x = (members.index(key) + x) / len(members)
            result.append((x, y, _[0] if _ else 0))
        return tuple(result)

    def join_points(self, entries, leader, total):
        try:
            return self.mapped_points(self.devices[leader], total)
        except ValueError:
            pass
        layout_ids = {(self.devices[key].layout or {}).get("uuid") for key in entries}
        if len(layout_ids) != 1 or not next(iter(layout_ids)):
            raise ValueError(f"Join needs a complete map of all {total} LEDs or matching physical mapping IDs on every controller. Refresh the group mapping in Twinkly.")
        points = {}
        for key, info in entries.items():
            device = self.devices[key]
            try:
                segment = self.mapped_points(device, device.row["leds"])
            except ValueError as exc:
                raise ValueError(f"{device.row.get('name', key)} returned an incomplete Join mapping. Refresh the group mapping in Twinkly.") from exc
            points.update((info["offset"] + index, point) for index, point in segment.items())
        return points

    def join_entries(self, members):
        for entries in self.native_memberships().values():
            if entries.keys() == set(members):
                return entries
        return {key: self.devices[key].native_group or {} for key in members}

    def validate_join(self, entries):
        masters = [key for key, info in entries.items() if info.get("role") == "master"]
        if not masters:
            raise ValueError("Join needs exactly one native master. Bring the master online, refresh discovery, or explicitly associate it on the Test page.")
        if len(masters) > 1:
            names = ", ".join(self.devices[key].row.get("name", key) for key in masters)
            raise ValueError(f"Multiple controllers report they are Join master ({names}). Check group membership in Twinkly.")
        sizes = {info.get("size") for info in entries.values()} - {None}
        if len(sizes) > 1:
            raise ValueError("Controllers report different Join LED totals. Check group membership in Twinkly.")
        missing = [self.devices[key].row.get("name", key) for key, info in entries.items() if info.get("offset") is None]
        if missing:
            raise ValueError(f"Join offset is missing for {', '.join(missing)}. Refresh discovery and check the group mapping in Twinkly.")
        if entries[masters[0]]["offset"] != 0:
            raise ValueError("The Join master must start at offset 0. Check member order in Twinkly.")
        expected = 0
        for key, info in sorted(entries.items(), key=lambda item: item[1].get("offset") or 0):
            offset = info.get("offset")
            if offset != expected:
                name = self.devices[key].row.get("name", key)
                raise ValueError(f"Join offset for {name} is {offset} (expected {expected}). Check member order and mapping in Twinkly.")
            expected += self.devices[key].row["leds"]
        if sizes and expected != next(iter(sizes)):
            raise ValueError(f"Join reports {next(iter(sizes))} LEDs but its members account for {expected}. Bring the missing controllers online and refresh discovery.")
        return masters[0], expected

    async def load_group_layouts(self, keys, mode):
        if mode == "join":
            master, total = self.validate_join(self.join_entries(keys))
            device = self.devices[master]
            if not await device.run(device.load_layout):
                raise ValueError(f"Could not read the physical mapping from {device.row['name']}. Check the controller connection and retry.")
            try:
                self.mapped_points(device, total)
            except ValueError:
                keys = [key for key in keys if key != master]
            else:
                return
        results = await asyncio.gather(*(self.devices[key].run(self.devices[key].load_layout) for key in keys))
        failed = [self.devices[key].row["name"] for key, ok in zip(keys, results) if not ok]
        if failed:
            raise ValueError(f"Could not read the physical mapping from {', '.join(failed)}. Check the controller connection and retry.")

    @staticmethod
    def group_conflict(group, operation, reason):
        LOG.warning("group=%s operation=%s rejected: %s", group, operation, reason)
        return web.json_response({"error": str(reason)}, status=409)

    def group_mapping(self, key, members, mode, matrix=False):
        result = []
        for x, y, z in self.group_coordinates(key, members, mode):
            pixel = min(11, int(x*12)) + 12*min(9, int(y*10)) if matrix else min(PIXELS-1, int(x*PIXELS))
            result.append(3*pixel)
        return tuple(result)

    @staticmethod
    def led_test_order(points):
        indices = range(len(points))
        return indices[::-1] if points and points[0][1] > points[-1][1] else indices

    @staticmethod
    def physical_frame(kind, index, coords, elapsed):
        if kind == "led":
            offset = 3 * coords[int(elapsed * 8) % len(coords)]
            frame = bytearray(3 * len(coords))
            frame[offset:offset+3] = bytes((90, 90, 90))
            return bytes(frame)
        palette = ((90,0,0),(0,90,0),(0,0,90),(90,90,0))
        def color(i, x, y):
            if kind == "identify": return palette[index % len(palette)]
            if kind == "rgb": return palette[int(elapsed / 2) % 3]
            if kind == "rainbow": return tuple(round(v*90) for v in colorsys.hsv_to_rgb((x-elapsed/6)%1,1,1))
            position = x if kind == "horizontal" else y
            return (90,90,90) if abs(position-(elapsed/4)%1)<.08 else (0,0,0)
        return bytes(v for i,(x,y,z) in enumerate(coords) for v in color(i,x,y))

    async def physical_test(self, request):
        data = await request.json()
        if not isinstance(data, dict) or not isinstance(data.get("group"), str):
            raise web.HTTPBadRequest()
        kind = data.get("test")
        if kind not in ("identify","rgb","led","rainbow","horizontal","vertical","stop"):
            raise web.HTTPBadRequest()
        async with self.edit:
            group = self.display_groups().get(data["group"])
            if not group:
                raise web.HTTPNotFound()
            keys = [k for k in group["members"] if k in self.devices]
            if kind == "stop":
                for k in keys:
                    self.physical_tests.pop(k,None)
                return web.json_response({"ok":True})
            if any(k in self.patterns or k in self.music or k in self.sequence_devices or self.devices[k].restore is not None for k in keys):
                return self.group_conflict(data["group"], kind, "Stop active music, effects and sequences first.")
            mode = group.get("mode","sync")
            if kind in ("identify","rgb"):
                coordinates = {k: [(0,0,0)]*self.devices[k].row["leds"] for k in keys}
            else:
                try:
                    await self.load_group_layouts(keys, mode)
                    if kind == "led":
                        coordinates = {k: self.led_test_order(self.group_coordinates(k, keys, mode, apply_reverse=False))
                                       for k in keys}
                    else:
                        coordinates = {k:self.group_coordinates(k,keys,mode) for k in keys}
                except ValueError as exc:
                    if kind != "led":
                        return self.group_conflict(data["group"], kind, exc)
                    LOG.warning("group=%s operation=led using controller order: %s", data["group"], exc)
                    coordinates = {k: range(self.devices[k].row["leds"]) for k in keys}
            start = time.monotonic()
            for index,k in enumerate(keys):
                self.physical_tests[k] = (kind,index,coordinates[k],start)
            LOG.info("physical test group=%s type=%s members=%s duration=15s",data["group"],kind,keys)
            return web.json_response({"ok":True,"duration":15})

    async def group_layout(self, request):
        group = self.display_groups().get(request.query.get("id"))
        if not group:
            raise web.HTTPNotFound()
        keys = [k for k in group["members"] if k in self.devices]
        mode = group.get("mode", "sync")
        try:
            await self.load_group_layouts(keys, mode)
            members = [{"id":k, "name":self.devices[k].row["name"],
                        "points":self.group_coordinates(k,keys,mode)} for k in keys]
        except ValueError as exc:
            return self.group_conflict(request.query.get("id"), "layout", exc)
        return web.json_response({"mode":mode,"members":members,"leds":sum(len(m["points"]) for m in members)})

    def shared_pattern(self, pattern, tick):
        cached = self.group_frames.get(pattern)
        if cached is not None and cached[0] == tick:
            return cached[1]
        if pattern.startswith(("gif:", "matrix:")):
            timing, frames = self.gif_patterns[pattern]
            frame = frames[bisect.bisect_right(timing, (tick * 1000 // self.fps) % timing[-1])]
        else:
            frame = live_pattern(pattern, tick, self.fps)
        self.group_frames[pattern] = (tick, frame)
        return frame

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
            test = self.physical_tests.get(key)
            if test and now-test[3] >= 15:
                self.physical_tests.pop(key,None)
                test = None
            if now >= device.retry:
                if test:
                    kind,index,coords,start = test
                    frame = self.physical_frame(kind,index,coords,now-start)
                    await device.run(device.send,frame,range(0,len(frame),3),automatic=True)
                elif pattern:
                    frame = self.shared_pattern(pattern, int(now * self.fps))
                    level = self.sequence_devices.get(key, 100)
                    await device.run(device.send, self.dim_frame(frame, level), self.group_routes.get(key), automatic=True)
                elif active:
                    fade_started = None
                    level = (self.show["master"] * self.sequence_devices.get(key, 100)
                             * self.mixed_music_levels.get(key, 100) // 10000)
                    frame = self.dim_frame(self.ddp.frame, level)
                    if any(frame):
                        last_output = frame
                    await device.run(device.send, frame, self.group_routes.get(key), automatic=True)
                elif device.restore is not None:
                    rule = self.silence_mode(key) if armed else "restore"
                    if rule == "fade" and last_output is not None:
                        fade_started = fade_started or now
                        remaining = max(0, 100 - int((now - fade_started) * 100))
                        if remaining:
                            fading = True
                            await device.run(device.send, self.dim_frame(last_output, remaining), self.group_routes.get(key), automatic=True)
                        elif await device.run(device.set_mode, "off", automatic=True):
                            device.restore = None
                    elif rule == "fade":
                        if await device.run(device.set_mode, "off", automatic=True):
                            device.restore = None
                    elif rule == "warm":
                        if await device.run(device.color, (255, 190, 110), automatic=True):
                            device.restore = None
                    else:
                        await device.run(device.command, "stop", None, automatic=True)
                    if not fading:
                        device.rt_check = 0
                        last_output = None
                        fade_started = None
                elif now >= device.mode_check:
                    device.mode_check = now + 30
                    if not await device.run(device.read_mode, automatic=True):
                        device.mode = None
                    else:
                        if not device.model_checked:
                            await device.run(device.read_product_code, automatic=True)
                        if now >= device.native_group_until:
                            await device.run(device.load_native_group, automatic=True)
            await asyncio.sleep(1 / self.fps if pattern or active or fading else 0.2)

    async def stream(self, app):
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: self.ddp, local_addr=("127.0.0.1" if self.source == "127.0.0.1" else "0.0.0.0", DDP_PORT)
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
        self.group_routes.clear()
        self.group_frames.clear()
        await asyncio.gather(*(d.run(d.command, "stop", None) for d in self.devices.values()))
        for _, task in workers.values():
            task.cancel()
        await asyncio.gather(*(task for _, task in workers.values()), return_exceptions=True)
        self.realtime_socket.close()

    async def status(self, request):
        return web.json_response({
            "audio": self.ddp.frame is not None and time.monotonic() - self.ddp.received < 1.5,
            "groups": {
                key: dict(group, members=[member for member in group["members"] if member in self.devices])
                for key, group in self.groups.items()
            },
            "display_groups": self.display_groups(),
            "sequence": self.sequence_status,
            "sequence_error": self.sequence_error,
            "sequence_data": self.sequence_data,
            "active_music_style": self.active_style,
            "show": self.show,
            "devices": [dict(d.row, music=k in self.music, mode=d.mode, offline=d.offline, error=d.error, product_code=d.product_code, pattern=self.patterns.get(k))
                        for k, d in self.devices.items()],
        })

    async def network(self, request):
        async with self.network_lock:
            devices = list(self.devices.values())
            if time.monotonic() >= self.network_until or devices != self.network_devices:
                await asyncio.gather(*(self.observe_wifi(device) for device in devices))
                self.network_devices = devices
                self.network_until = time.monotonic() + 30
            rows = [self.network_row(device) for device in self.devices.values()]

        for row in rows:
            if row["kind"] != "wifi":
                continue
            peers = [peer for peer in rows if peer["id"] != row["id"] and peer["kind"] == "ap"
                     and peer["ssid"] == row["ssid"] and peer["ap_ip"] == row["gateway"]]
            if len(peers) == 1:
                row["peer"] = peers[0]["id"]
        return web.json_response({"devices": rows, "groups": self.display_groups()}, headers={"Cache-Control": "no-store"})

    def display_groups(self):
        groups = {
            key: dict(group, members=[member for member in group["members"] if member in self.devices])
            for key, group in self.groups.items()
        }
        for key, group in self.native_groups().items():
            local = next((local for local in groups.values()
                          if set(group["members"]) == set(local["members"])), None)
            if local is None:
                groups[key] = group
            else:
                local["native"] = True
                if group["mode"] == "join":
                    local["members"] = group["members"]
                    local.setdefault("mode", group["mode"])
                    for field in ("layout_size", "missing_master", "manual_master"):
                        if field in group:
                            local[field] = group[field]
        return groups

    def native_memberships(self):
        by_id = {}
        for key, device in self.devices.items():
            info = device.native_group
            if info and info.get("id"):
                by_id.setdefault(info["id"], {})[key] = info

        recoveries = {}
        for group_id, entries in by_id.items():
            if any(info["role"] == "master" for info in entries.values()):
                continue
            references = {info["master_id"].casefold() for info in entries.values() if info.get("master_id")}
            if len(references) != 1:
                continue
            reference = next(iter(references))
            candidates = []
            for key, device in self.devices.items():
                info = device.native_group or {}
                if key in entries or info.get("role") == "slave" or info.get("uid"):
                    continue
                identities = {value.strip().casefold() for value in getattr(device, "native_identity", {}).values()}
                if info.get("id"):
                    identities.add(info["id"].casefold())
                if reference in identities:
                    candidates.append(key)
            if len(candidates) == 1:
                recoveries.setdefault(candidates[0], []).append(group_id)

        for key, group_ids in recoveries.items():
            if len(group_ids) == 1:
                group_id = group_ids[0]
                info = self.devices[key].native_group or {}
                previous = by_id.get(info.get("id"), {})
                if len(previous) <= 1:
                    previous.pop(key, None)
                    by_id[group_id][key] = dict(info, role="master", offset=0 if info.get("offset") is None else info["offset"])

        layout_recoveries = {}
        for group_id, entries in by_id.items():
            if not entries or any(info["role"] != "slave" for info in entries.values()):
                continue
            layout_ids = {self.devices[key].native_layout_id for key in entries}
            if len(layout_ids) != 1 or not next(iter(layout_ids)):
                continue
            layout_id = next(iter(layout_ids))
            if not any(info.get("size") for info in entries.values()):
                continue
            candidates = []
            for key, device in self.devices.items():
                if (device.offline or device.native_layout_id != layout_id or not device.native_standalone
                        or device.native_group is not None or device.row.get("native_master_for") not in (None, group_id)):
                    continue
                proposed = dict(entries, **{key: {"role": "master", "offset": 0}})
                try:
                    self.validate_join(proposed)
                except ValueError:
                    continue
                candidates.append(key)
            if len(candidates) == 1:
                layout_recoveries.setdefault(candidates[0], []).append(group_id)
        for key, group_ids in layout_recoveries.items():
            if len(group_ids) == 1:
                by_id[group_ids[0]][key] = {"role": "master", "offset": 0}

        for group_id, entries in by_id.items():
            manual = [key for key, device in self.devices.items()
                      if device.row.get("native_master_for") == group_id
                      and self.manual_master_candidate(key, entries)]
            if len(manual) == 1:
                proposed = dict(entries, **{manual[0]: {"role": "master", "offset": 0, "manual": True}})
                try:
                    self.validate_join(proposed)
                except ValueError:
                    continue
                by_id[group_id] = proposed
        return by_id

    def manual_master_candidate(self, key, entries):
        info = self.devices[key].native_group or {}
        return (info.get("role") in (None, "master") and not info.get("id")
                and all(entry["role"] != "master" for entry in entries.values()))

    def native_groups(self):
        groups = {}
        for group_id, membership in self.native_memberships().items():
            entries = list(membership.items())
            leaders = [key for key, info in entries if info["role"] == "master"]
            has_uid = any(info.get("uid") for _, info in entries)
            if not entries or (len(entries) < 2 and not has_uid) or (not leaders and not has_uid):
                continue
            entries.sort(key=lambda entry: (
                entry[1].get("offset") is None, entry[1].get("offset") or 0))
            members = [key for key, _ in entries]
            names = {info["name"] for _, info in entries if info.get("name")}
            numbered = [re.fullmatch(r"(.+?)\s+\d+", self.devices[key].row["name"].strip())
                        for key in members]
            prefixes = {match[1] for match in numbered if match}
            name = self.devices[(leaders or members)[0]].row["name"]
            if len(names) == 1:
                name = next(iter(names))
            elif all(numbered) and len(prefixes) == 1:
                name = next(iter(prefixes))
            group = {"name": name, "members": members, "mode": "sync"}
            sizes = {info["size"] for _, info in entries if info.get("size") is not None}
            joined = any((info.get("offset") or 0) > 0 for _, info in entries)
            joined |= bool(has_uid and sizes and max(sizes) > max(self.devices[k].row["leds"] for k in members))
            if joined:
                if len(sizes) == 1:
                    group["layout_size"] = next(iter(sizes))
                group["mode"] = "join"
                if not leaders:
                    group["missing_master"] = "native:" + group_id
                if len(leaders) == 1 and membership[leaders[0]].get("manual"):
                    group["manual_master"] = {"group": "native:" + group_id, "device": leaders[0]}
            elif len(entries) < 2:
                continue
            key = "native:" + group_id
            group["name"] = self.native_group_names.get(key, group["name"])
            groups[key] = group
        return groups

    async def associate_native_master(self, request):
        data = await request.json()
        group = data.get("group") if isinstance(data, dict) else None
        key = data.get("device") if isinstance(data, dict) else None
        if not isinstance(group, str) or not group.startswith("native:") or not isinstance(key, str):
            raise web.HTTPBadRequest()
        group_id = group.removeprefix("native:")
        async with self.edit:
            device = self.devices.get(key)
            if device is None:
                raise web.HTTPNotFound()
            field = "native_master_for"
            if data.get("remove") is True:
                if device.row.get("native_master_for") != group_id:
                    raise web.HTTPNotFound()
                value = None
            else:
                entries = self.native_memberships().get(group_id)
                try:
                    group_info = self.native_groups().get(group, {})
                    if not group_info.get("missing_master") or not entries or not self.manual_master_candidate(key, entries) or device.row.get(field):
                        raise ValueError("Choose an unassociated controller for a Join group with a missing master.")
                    if not any(info.get("size") for info in entries.values()):
                        raise ValueError("Twinkly must report the full Join LED total before a master can be associated.")
                    _, total = self.validate_join(dict(entries, **{key: {"role": "master", "offset": 0}}))
                    device.layout_until = 0
                    if not await device.run(device.load_layout):
                        raise ValueError(f"Could not read {device.row['name']}'s mapping. Check its connection and retry.")
                    try:
                        self.mapped_points(device, total)
                    except ValueError as exc:
                        raise ValueError(f"{device.row['name']} needs a complete physical map for all {total} LEDs.") from exc
                    current = self.native_memberships().get(group_id)
                    if current != entries or not self.manual_master_candidate(key, current):
                        raise ValueError("Native group membership changed during validation. Refresh and retry.")
                except ValueError as exc:
                    return self.group_conflict(group, "associate master", exc)
                value = group_id
            previous = device.row.get(field)
            if value is None:
                device.row.pop(field)
            else:
                device.row[field] = value
            try:
                self.save()
            except OSError:
                if previous is None:
                    device.row.pop(field, None)
                else:
                    device.row[field] = previous
                raise
            LOG.info("group=%s explicit master device=%s removed=%s", group, key, value is None)
        return web.json_response({"ok": True})

    async def rename_network_group(self, request):
        data = await request.json()
        if not isinstance(data, dict):
            raise web.HTTPBadRequest()
        key, name = data.get("id"), data.get("name")
        if not isinstance(key, str) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise web.HTTPBadRequest()
        name = name.strip()
        async with self.edit:
            if key in self.groups:
                updated = dict(self.groups, **{key: dict(self.groups[key], name=name)})
                temp = GROUPS.with_suffix(".tmp")
                temp.write_text(json.dumps(updated), encoding="utf-8")
                temp.replace(GROUPS)
                self.groups = updated
            else:
                if key not in self.native_groups():
                    raise web.HTTPNotFound()
                updated = dict(self.native_group_names, **{key: name})
                temp = self.native_group_names_path.with_suffix(".tmp")
                temp.write_text(json.dumps(updated), encoding="utf-8")
                temp.replace(self.native_group_names_path)
                self.native_group_names = updated
        return web.json_response({"name": name})

    async def observe_wifi(self, device):
        ok = await device.run(device.load_details, automatic=True)
        details = (device.details or {}) if ok and not device.offline else {}
        ssid = details.get("ssid")
        station_ip = details.get("ip")
        if (details.get("network_mode") != 1 or details.get("status") not in (None, 5, "5")
                or not isinstance(ssid, str) or not station_ip or station_ip == "0.0.0.0"):
            device.wifi_observation = None
            device.network_details = details
            return
        measured_at = device.details_until - 60
        identity = (ssid, station_ip, details.get("gw"), details.get("bssid"))
        previous = device.wifi_observation
        since = measured_at
        if previous and previous[0] == identity and measured_at - previous[2] <= 100:
            since = previous[1]
        device.wifi_observation = (identity, since, measured_at)
        device.network_details = details

    @staticmethod
    def network_row(device):
        row = {key: device.row[key] for key in ("id", "name", "ip")}
        details = device.network_details
        if device.native_group and not device.offline:
            row["group_role"] = device.native_group["role"]
        row["kind"] = "unknown"
        if device.offline:
            row["kind"] = "offline"
        elif device.wifi_observation:
            (ssid, _, gateway, bssid), since, measured_at = device.wifi_observation
            rssi = details.get("rssi")
            try:
                rssi = float(rssi)
            except (TypeError, ValueError):
                rssi = None
            row.update(kind="wifi", ssid=ssid, gateway=gateway, bssid=bssid,
                       rssi=rssi if rssi is not None and -120 <= rssi < 0 else None,
                       channel=details.get("channel"), seconds=max(0, int(measured_at - since)))
        elif details.get("network_mode") == 2 and details.get("ap_ssid"):
            ap_ip = details.get("ap_ip")
            row.update(kind="ap", ssid=details["ap_ssid"],
                       ap_ip=ap_ip if ap_ip and ap_ip != "0.0.0.0" else row["ip"],
                       channel=details.get("channel"))
        return row

    async def remove_device(self, request):
        key = (await request.json()).get("id")
        if not isinstance(key, str):
            raise web.HTTPBadRequest()
        async with self.edit:
            device = self.devices.get(key)
            if device is None:
                return web.json_response({"ok": True})
            async with device.lock:
                if not device.offline:
                    return web.json_response({"ok": False})
                self.save(exclude=key)
                device.removed = True
                del self.devices[key]
                self.music.discard(key)
                self.patterns.pop(key, None)
                self.sequence_devices.pop(key, None)
                device.client.session.close()
                LOG.info("lamp=%r ip=%s actie=verwijderen status=offline", device.row["name"], device.row["ip"])
        return web.json_response({"ok": True})

    async def register(self, request):
        data = await request.json()
        async with self.edit_scan:
            hosts = [data["ip"]] if data.get("ip") else await asyncio.to_thread(discover, self.broadcast)
            if not hosts:
                return web.json_response({"added": 0, "errors": [
                    "Geen Twinkly-antwoord op UDP-poort 5555. Controleer of de lampen op hetzelfde LAN zitten of voeg hun IP-adres toe."
                ]})
            results = await asyncio.gather(*(self.add(host) for host in hosts), return_exceptions=True)
        errors = []
        for host, result in zip(hosts, results):
            if not isinstance(result, Exception):
                continue
            LOG.warning("ip=%s actie=registreren: %s", host, result)
            if isinstance(result, (LampConnectionError, Timeout)):
                errors.append(f"{host}: offline")
            else:
                errors.append(f"{host}: {result}")
        return web.json_response({"added": sum(isinstance(x, dict) for x in results), "errors": errors})

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
                        or mode not in ("music", "off") or len(scenes) >= MAX_SAVED_SCENES):
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
                if group_id is None and len(groups) >= MAX_SAVED_GROUPS:
                    raise web.HTTPBadRequest()
                silence = data.get("silence", "restore")
                if silence not in SILENCE_MODES:
                    raise web.HTTPBadRequest()
                mode = data.get("mode", "sync")
                if mode not in ("join", "sync", "area"):
                    raise web.HTTPBadRequest()
                groups[group_id or uuid.uuid4().hex] = {
                    "name": name.strip(), "members": list(dict.fromkeys(members)), "silence": silence, "mode": mode
                }
            temp = GROUPS.with_suffix(".tmp")
            temp.write_text(json.dumps(groups), encoding="utf-8")
            temp.replace(GROUPS)
            self.groups = groups
        return web.json_response({"ok": True})

    @staticmethod
    def image_path(key, kind, index):
        fingerprint = hashlib.sha256(f"{key}/{kind}/{index}".encode()).hexdigest()
        return asset_path(IMAGES, fingerprint + ".jpg")

    @staticmethod
    def effect_gif_path(key, entry):
        identity = entry.get("unique_id") or (entry["id"], entry["name"])
        fingerprint = hashlib.sha256(json.dumps([key, entry["kind"], identity]).encode()).hexdigest()
        return asset_path(IMAGES, fingerprint + ".gif")

    @staticmethod
    def bundled_effect_image(entry):
        name = entry.get("name")
        if entry["kind"] != "movie" or not isinstance(name, str):
            return None
        filename = BUNDLED_EFFECT_PREVIEWS.get(" ".join(name.casefold().split()))
        if filename is None:
            return None
        path = asset_path(EFFECT_PREVIEWS, filename)
        return path if path.is_file() else None

    async def twinkly_wordmark(self, request):
        return web.FileResponse(WORDMARK, headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "private, max-age=86400",
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'",
            "X-Content-Type-Options": "nosniff",
        })

    async def product_photo(self, request):
        key = request.match_info["key"]
        if key not in PRODUCT_PHOTO_KEYS:
            raise web.HTTPNotFound()
        path = asset_path(PRODUCT_PHOTOS, key + ".png")
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400",
                                               "X-Content-Type-Options": "nosniff"})

    async def effect_image(self, request):
        key = request.query.get("id")
        kind = request.query.get("kind")
        index = request.query.get("index", "")
        device = self.devices.get(key)
        if device is None or kind not in ("movie", "effect") or not re.fullmatch(r"[0-9]{1,3}", index):
            raise web.HTTPNotFound()
        index = int(index)
        entry = next((item for item in device.effects if item["kind"] == kind and item["id"] == index), None)
        if entry is None:
            raise web.HTTPNotFound()
        gif = self.effect_gif_path(key, entry)
        still = self.image_path(key, kind, index)
        if request.query.get("ref", gif.stem) != gif.stem:
            raise web.HTTPNotFound()
        if request.method == "GET":
            path = gif if gif.is_file() else still
            if not path.is_file():
                path = self.bundled_effect_image(entry)
            if path is None:
                raise web.HTTPNotFound()
            return web.FileResponse(path, headers={"Cache-Control": "no-cache", "X-Content-Type-Options": "nosniff"})
        data = await request.json()
        if not isinstance(data, dict) or "image" not in data:
            raise web.HTTPBadRequest()
        image = data["image"]
        if image is None:
            gif.unlink(missing_ok=True)
            still.unlink(missing_ok=True)
            return web.json_response({"ok": True})
        try:
            raw = base64.b64decode(image, validate=True)
            if raw.startswith((b"GIF87a", b"GIF89a")):
                await asyncio.to_thread(self.decode_gif, raw)
                path, previous = gif, still
            elif (4 <= len(raw) <= 160_000 and raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9")):
                path, previous = still, gif
            else:
                raise ValueError("Unsupported preview format")
        except (ValueError, TypeError, OSError, SyntaxError, Image.DecompressionBombError) as exc:
            raise web.HTTPBadRequest() from exc
        IMAGES.mkdir(exist_ok=True)
        write_asset(path, raw)
        previous.unlink(missing_ok=True)
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
            group = None
            if group_id is not None:
                if not isinstance(group_id, str) or action == "effect":
                    raise web.HTTPBadRequest()
                group = self.display_groups().get(group_id)
                if not group:
                    raise web.HTTPBadRequest()
                keys = [key for key in group["members"] if key in self.devices]
            else:
                keys = list(self.devices) if data.get("id") == "*" else [data.get("id")]
            if any(key not in self.devices for key in keys):
                raise web.HTTPNotFound()
            for k in keys:
                self.physical_tests.pop(k,None)
            routes = {}
            if group and action in ("pattern", "music"):
                mode = group.get("mode", "sync")
                try:
                    await self.load_group_layouts(keys, mode)
                    routes = {k: self.group_mapping(k, keys, mode, matrix=action == "pattern" and value.startswith("matrix:")) for k in keys}
                    for k in keys:
                        d = self.devices[k]
                        meta = d.native_group or {}
                        route = routes[k]
                        LOG.info("mapping lamp=%r mode=%s role=%s offset=%s size=%s leds=%s points=%s route_first=%s route_last=%s",
                                 d.row["name"], mode, meta.get("role"), meta.get("offset"), meta.get("size"), d.row["leds"],
                                 len((d.layout or {}).get("points", [])), route[:8] if route else None, route[-8:] if route else None)
                except ValueError as exc:
                    raise web.HTTPBadRequest(text=str(exc)) from exc
            if action == "pattern":
                if value.startswith(("gif:", "matrix:")) and value not in self.gif_patterns:
                    kind, gif_id = value.split(":", 1)
                    root, pattern = (MATRIX_GIFS, MATRIX_ID) if kind == "matrix" else (GIF_LIBRARY, GIF_ID)
                    try:
                        self.gif_patterns[value] = await asyncio.to_thread(
                            self.decode_gif, gif_asset(root, gif_id, pattern).read_bytes(), kind == "matrix")
                    except (OSError, ValueError, web.HTTPNotFound) as exc:
                        raise web.HTTPBadRequest(text="GIF unavailable") from exc
                self.music.difference_update(keys)
                self.patterns.update(dict.fromkeys(keys, value))
                for k in keys:
                    self.group_routes[k] = routes.get(k)
                self.mark_sequence_devices(keys, sequence_level)
                return {"failed": []}
            if action == "stop-pattern":
                keys = [key for key in keys if key in self.patterns]
                action = "stop"
            for key in keys:
                self.patterns.pop(key, None)
            self.mark_sequence_devices(keys, sequence_level if action == "music" else None)
            if action == "music":
                for k in keys:
                    self.group_routes[k] = routes.get(k)
                self.music.update(keys)
                return {"failed": []}
            self.music.difference_update(keys)
            for k in keys:
                self.group_routes.pop(k, None)
            results = await asyncio.gather(*(self.devices[k].run(self.devices[k].command, action, value)
                                             for k in keys))
            failures = [self.devices[key] for key, ok in zip(keys, results) if not ok]
            return {
                "failed": [device.row["name"] for device in failures if not device.offline],
                "offline": [device.row["name"] for device in failures if device.offline],
            }

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
                                  "settings": device.row.get("mapping_override", {}),
                                  "error": None if ok else device.error})

    @staticmethod
    def mapping_device_info(d, fresh):
        details = d.details or {}
        fields = ("product_name", "product_code", "product_version", "hardware_version",
                  "firmware_version", "fw_family", "led_profile", "bytes_per_led", "led_type",
                  "number_of_led", "rssi")
        info = {key: details.get(key) for key in fields}
        info["product_code"] = info["product_code"] or d.product_code
        info.update(name=d.row["name"], leds=d.row["leds"],
                    metadata_status="available" if fresh else ("cached" if details else "unavailable"))
        return info

    async def mapping_settings(self, request):
        d = self.devices.get(request.query.get("id"))
        if d is None:
            raise web.HTTPNotFound()
        if request.method == "POST":
            data = await request.json()
            if not isinstance(data, dict) or type(data.get("rotation")) is not int or data["rotation"] not in (0,90,180,270) or any(type(data.get(k)) is not bool for k in ("mirror_x","mirror_y","reverse")):
                raise web.HTTPBadRequest(text="Invalid mapping settings")
            updated = {k:data[k] for k in ("rotation","mirror_x","mirror_y","reverse")}
            async with self.edit:
                old = d.row.get("mapping_override", {})
                d.row["mapping_override"] = updated
                try:
                    self.save()
                except OSError:
                    d.row["mapping_override"] = old
                    raise
                LOG.info("mapping settings lamp=%r old=%s new=%s", d.row["name"], old, updated)
        fresh = await d.run(d.load_details) if request.method == "GET" else False
        return web.json_response({"settings":d.row.get("mapping_override", {}), "group":d.native_group,
                                  "layout":d.layout, "device":self.mapping_device_info(d, fresh)})

    async def effects(self, request):
        device = self.devices.get(request.query.get("id"))
        if device is None:
            raise web.HTTPNotFound()
        ok = await device.run(device.load_effects)
        catalog = []
        if ok:
            key = device.row["id"]
            for entry in device.effects:
                gif = self.effect_gif_path(key, entry)
                still = self.image_path(key, entry["kind"], entry["id"])
                custom = gif.is_file() or still.is_file()
                bundled = self.bundled_effect_image(entry) is not None
                catalog.append(dict(entry, preview_ref=gif.stem, has_image=custom or bundled,
                                    has_custom_image=custom, has_default_image=bundled))
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
        path = gif_asset(MATRIX_GIFS, key, MATRIX_ID)
        return web.FileResponse(path, headers={
            "Content-Type": "image/gif", "X-Content-Type-Options": "nosniff",
        })

    async def list_gifs(self, request):
        if GIF_LIBRARY.is_symlink():
            raise web.HTTPNotFound()
        entries = [{"id": path.stem, "name": path.stem.split("-", 1)[1].replace("_", " ")}
                   for path in sorted(GIF_LIBRARY.glob("*.gif"))
                   if GIF_ID.fullmatch(path.stem) and not path.is_symlink() and path.is_file()]
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
                gif_asset(GIF_LIBRARY, gif_id, GIF_ID).unlink(missing_ok=True)
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
            path = gif_asset(GIF_LIBRARY, gif_id, GIF_ID)
            GIF_LIBRARY.mkdir(exist_ok=True)
            if not path.is_file():
                if sum(1 for _ in GIF_LIBRARY.glob("*.gif")) >= 30:
                    raise web.HTTPConflict(text="GIF library is full")
                write_asset(path, raw)
            self.gif_patterns["gif:" + gif_id] = decoded
        return web.json_response({"id": gif_id})

    async def gif_file(self, request):
        gif_id = request.match_info["id"]
        path = gif_asset(GIF_LIBRARY, gif_id, GIF_ID)
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
        background = Image.new("RGB", (300, 320), "#101927")
        draw = ImageDraw.Draw(background)
        draw.ellipse((36, 286, 264, 311), fill="#233347")
        draw.rectangle((138, 256, 162, 296), fill="#79503c")
        for top, bottom, half_width in ((115, 281, 121), (69, 217, 96), (34, 158, 68)):
            draw.polygon([(150, top), (150 - half_width, bottom),
                          (150 + half_width, bottom)], fill="#153f35", outline="#286353")
        star = []
        for i in range(10):
            angle = math.tau * i / 10 - math.pi / 2
            radius = 15 if i % 2 == 0 else 6
            star.append((150 + radius * math.cos(angle), 34 + radius * math.sin(angle)))
        draw.polygon(star, fill="#ffe099")

        points = []
        for i in range(PIXELS):
            row, column = divmod(i, 12)
            y = 270 - row * 22
            width = (y - 30) * 0.44
            position = (column + 0.5) / 12
            if row % 2:
                position = 1 - position
            points.append((round(150 + (2 * position - 1) * width), y - round(7 * math.sin(math.pi * position))))

        images = []
        for frame in frames:
            image = background.copy()
            draw = ImageDraw.Draw(image)
            for i, (x, y) in enumerate(points):
                color = tuple(frame[i * 3:i * 3 + 3])
                glow = tuple(int(channel * 0.26) for channel in color)
                draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill=glow)
                draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=color)
            images.append(image.quantize(colors=128))
        with io.BytesIO() as output:
            images[0].save(output, format="GIF", save_all=True,
                           append_images=images[1:], duration=100, loop=0)
            return output.getvalue()

    @staticmethod
    @functools.lru_cache(maxsize=len(MUSIC_STYLES))
    def demo_music_gif(style):
        frames = []
        for tick in range(30):
            time = tick / 30
            beat = (0.5 + 0.5 * math.cos(math.tau * time * 3)) ** 3
            frame = bytearray()
            for i in range(PIXELS):
                x = i / PIXELS
                wave = 0.5 + 0.5 * math.cos(math.tau * (x * 2 - time))
                sweep = (0.5 + 0.5 * math.cos(math.tau * (x - time))) ** 12
                phase = math.tau * time
                band = i // 24
                band_level = 0.5 + 0.5 * math.sin(phase + band * 1.7)
                hue, level = {
                    "energy": (0.76 + x * 0.15, 0.16 + 0.84 * beat * wave),
                    "spectrum": (x + time, 0.28 + 0.72 * wave),
                    "power": (0.02 + x * 0.1, 0.12 + 0.88 * (x < 0.28 + beat * 0.68)),
                    "wavelength": (0.48 + 0.22 * wave, 0.24 + 0.76 * wave),
                    "strobe": (0.14, 0.18 + 0.8 * (tick < 3)),
                    "scroll": (0.3 + 0.14 * wave, 0.14 + 0.86 * sweep),
                    "bands": ((i // 24) / 5, 0.2 + 0.8 * (beat if (i // 24) % 2 else wave)),
                    "blade_power_plus": (0.82 + 0.18 * wave, 0.12 + 0.88 * max(sweep, beat * wave)),
                    "magnitude": (0.56, 0.12 + 0.88 * (abs(x - 0.5) < 0.10 + beat * 0.38)),
                    "fire": (0.015 + 0.1 * wave, (1 - x) * (0.38 + 0.62 * wave)),
                    "rain": (0.58, 0.10 + 0.9 * (1 - (3 * x + time * 2) % 1) ** 8),
                    "melt": (0.88 + 0.22 * wave, 0.32 + 0.68 * wave),
                    "melt_and_sparkle": (0.12 + x * 0.1, 0.24 + 0.76 * max(wave * 0.5, (0.5 + 0.5 * math.cos(i * 2.4 + math.tau * time)) ** 18)),
                    "scan": (0.94, 0.08 + 0.92 * sweep),
                    "water": (0.47 + 0.14 * wave, 0.24 + 0.76 * wave ** 2),
                    "energy2": (time + x * 0.25, 0.12 + 0.88 * wave * (0.45 + beat * 0.55)),
                    "bar": (0.07 + time, 0.09 + 0.91 * ((x - time * 3) % 1 < 0.45)),
                    "blocks": (band / 5 + time, 0.18 + 0.82 * band_level ** 2),
                    "equalizer": (0.36 - x * 0.28, 0.1 + 0.9 * (i % 24 < band_level * 24)),
                    "lava_lamp": (0.82 + wave * 0.23, 0.18 + 0.82 * wave ** 3),
                    "pitchSpectrum": (time + band / 5, 0.16 + 0.84 * band_level * wave),
                    "scan_multi": (x + 0.35, 0.1 + 0.9 * wave ** 14),
                    "scan_and_flare": (0.10 + 0.44 * (1 - sweep), 0.16 + 0.84 * max(sweep, beat * wave)),
                    "scroll_plus": (0.55 + 0.28 * wave, 0.15 + 0.85 * max(sweep, wave ** 5)),
                    "vumeter": (0.33 * (1 - x), 0.08 + 0.92 * (x < 0.25 + 0.74 * beat)),
                    "multiBar": (band / 5, 0.1 + 0.9 * ((x * 5 - time * 2 + band * 0.36) % 1 < 0.35)),
                }[style]
                saturation = 0.06 if style == "strobe" else 0.86
                frame.extend(int(channel * 255) for channel in colorsys.hsv_to_rgb(hue % 1, saturation, level))
            frames.append(bytes(frame))
        return Controller.encode_gif(frames)

    async def music_demo(self, request):
        style = request.match_info["style"]
        if style not in MUSIC_STYLES:
            raise web.HTTPNotFound()
        result = await asyncio.to_thread(self.demo_music_gif, style)
        return web.Response(body=result, content_type="image/gif",
                            headers={"Cache-Control": "private, max-age=3600"})

    async def music_gif(self, request):
        if self.gif_capture.locked():
            raise web.HTTPConflict()
        async with self.gif_capture:
            frames = []
            for _ in range(30):
                frame = self.music_frame()
                if frame is None:
                    raise web.HTTPServiceUnavailable()
                frames.append(self.dim_frame(frame, self.show["master"]))
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
                LOG.warning("LedFX setup failed: %s", type(exc).__name__)
                return web.json_response({"ok": False, "message": "LedFX koppelen mislukt. Controleer LedFX en Music Assistant."})
        return web.json_response({
            "ok": True,
            "message": "LedFX ingesteld. Voeg LedFx Twinkly toe aan de afspeelgroep in Music Assistant en start muziek."
        })

    def app(self):
        self.edit_scan = asyncio.Lock()
        self.network_lock = asyncio.Lock()
        self.network_until = 0
        self.network_devices = []
        app = web.Application(middlewares=[ingress_only], client_max_size=720_000)
        from modules.security_center import install as install_security_center
        install_security_center(app, Path(__file__).resolve().parent, DATA.parent, ingress_only)
        from modules.provider_routes import install
        app.cleanup_ctx.append(self.stream)
        install(app, controller=self, govee_key=getattr(self, "govee_api_key", None))
        async def legacy_provider_page(request):
            raise web.HTTPFound("./#instellingen")

        app.router.add_get("/provider-studio", legacy_provider_page)
        for asset in (
            "lighting.js", "lighting-tools.js", "govee-cloud.js", "lighting.css", "twinkly-nav-logo.svg", "hue-app-icon.webp", "govee-logo.png",
            "project.html", "project.css", "project.js", "security-center.js", "CHANGELOG.md", "ROADMAP.md",
            "google-home.js", "google-home-demo.jpg", "google-home-show.jpg",
            "govee-guide-config.webp", "govee-guide-yaml.webp", "govee-guide-cloud.webp",
        ):
            app.router.add_get("/" + asset, lambda _, filename=asset: web.FileResponse(
                filename, headers={"Cache-Control": "no-store"}))
        app.router.add_get("/", lambda _: web.FileResponse(
            "index.html", headers={"Cache-Control": "no-store"}))
        app.router.add_get("/twinkly.svg", lambda _: web.FileResponse("twinkly.svg"))
        app.router.add_get("/twinkly-wordmark.svg", self.twinkly_wordmark)
        app.router.add_get("/healthz", health)
        app.router.add_get("/status", self.status)
        app.router.add_get("/network", self.network)
        app.router.add_post("/network/groups/name", self.rename_network_group)
        app.router.add_get("/effects", self.effects)
        app.router.add_get("/layout", self.layout)
        app.router.add_post("/physical-test", self.physical_test)
        app.router.add_get("/group-layout", self.group_layout)
        app.router.add_post("/network/groups/master", self.associate_native_master)
        app.router.add_get("/mapping-settings", self.mapping_settings)
        app.router.add_post("/mapping-settings", self.mapping_settings)
        app.router.add_get("/details", self.details)
        app.router.add_post("/register", self.register)
        app.router.add_post("/remove-device", self.remove_device)
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
        app.router.add_get("/music-demo/{style}", self.music_demo)
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
                raise ValueError(f"LedFX weigerde de opdracht (HTTP {response.status}).")
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

    config = {"name": "Twinkly Control Center", "ip_address": "127.0.0.1", "port": DDP_PORT,
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
    if request.path == "/healthz":
        if request.remote != "127.0.0.1":
            raise web.HTTPForbidden()
        return await handler(request)
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
    web.run_app(Controller(options).app(), host="0.0.0.0", port=HTTP_PORT, access_log=None)
