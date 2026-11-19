"""Verify offline status, app logs, recovery and removing saved devices."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer
from requests.exceptions import ConnectionError, HTTPError, Timeout

import app


ROW = {"id": "wall", "name": "Muur 3", "ip": "192.168.1.211",
       "leds": 210, "profile": "RGBW", "protocol": 3}


class OfflineDeviceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        data = Path(directory.name) / "devices.json"
        groups = data.with_name("groups.json")
        data.write_text(json.dumps([ROW]), encoding="utf-8")
        groups.write_text(json.dumps({"wall-group": {"name": "Muren", "members": ["wall"],
                                                      "silence": "restore"}}), encoding="utf-8")
        self.addCleanup(patch.stopall)
        patch.object(app, "DATA", data).start()
        patch.object(app, "GROUPS", groups).start()
        self.options = {"ddp_source": "127.0.0.1", "fps": 20}
        self.controller = app.Controller(self.options)
        self.addCleanup(self.controller.realtime_socket.close)
        self.device = self.controller.devices["wall"]
        self.addCleanup(lambda: self.device.client.session.close())
        server = self.controller.app()
        server.middlewares.clear()
        server.cleanup_ctx.clear()
        self.client = await self.enterAsyncContext(TestClient(TestServer(server)))

    async def get_status(self):
        response = await self.client.get("/status")
        self.assertEqual(response.status, 200)
        return await response.json()

    async def test_transport_failure_is_logged_and_safe_in_api(self):
        failure = ConnectionError("technical connection details")
        with patch.object(self.device, "command", side_effect=failure) as command:
            command.__name__ = "command"
            with self.assertLogs("twinkly", level="WARNING") as logged:
                for _ in range(2):
                    response = await self.client.post("/control", json={"id": "wall", "action": "on"})
                    self.assertEqual(await response.json(), {"offline": ["Muur 3"], "failed": []})
        self.assertEqual(len(logged.output), 2)
        self.assertIn("192.168.1.211 actie=on status=offline: technical connection details", logged.output[0])
        status = await self.get_status()
        self.assertTrue(status["devices"][0]["offline"])
        self.assertEqual(status["devices"][0]["error"], "offline")
        self.assertNotIn("technical connection details", json.dumps(status))

    async def test_only_a_reply_marks_device_online_again(self):
        def read_mode():
            raise Timeout("probe timed out")

        with self.assertLogs("twinkly", level="WARNING") as logged:
            for _ in range(2):
                self.assertFalse(await self.device.run(read_mode, automatic=True))
        self.assertEqual(len(logged.output), 1)
        self.assertTrue(await self.device.run(self.device.command, "stop", None))
        self.assertTrue(self.device.offline)

        def reply():
            self.device.replies += 1

        with self.assertLogs("twinkly", level="INFO") as logged:
            self.assertTrue(await self.device.run(reply, automatic=True))
        self.assertIn("status=online", logged.output[0])
        self.assertFalse((await self.get_status())["devices"][0]["offline"])

    async def test_http_failure_is_not_offline(self):
        def reject():
            raise HTTPError("private response")

        with self.assertLogs("twinkly", level="WARNING"):
            self.assertFalse(await self.device.run(reject))
        device = (await self.get_status())["devices"][0]
        self.assertFalse(device["offline"])
        self.assertEqual(device["error"], "device_error")

    async def test_network_links_only_to_a_matching_active_access_point(self):
        peer_row = dict(ROW, id="peer", name="Buiten", ip="192.168.1.1")
        peer = app.Device(peer_row, self.controller.limit, self.controller.realtime_socket)
        self.addCleanup(peer.client.session.close)
        self.controller.devices["peer"] = peer
        self.device.details = {"network_mode": 1, "ssid": "Twinkly-Buiten", "ip": ROW["ip"],
                               "gw": peer_row["ip"], "status": 5, "rssi": "-68"}
        peer.details = {"network_mode": 2, "ap_ssid": "Twinkly-Buiten", "ap_ip": peer_row["ip"]}
        self.device.details_until = peer.details_until = app.time.monotonic() + 60

        response = await self.client.get("/network")
        self.assertEqual(response.status, 200)
        station, access_point = (await response.json())["devices"]
        self.assertEqual((station["kind"], station["peer"], station["rssi"]), ("wifi", "peer", -68))
        self.assertEqual(access_point["kind"], "ap")

        peer.details = dict(peer.details, ap_ssid="Another SSID")
        self.controller.network_until = 0
        response = await self.client.get("/network")
        self.assertNotIn("peer", (await response.json())["devices"][0])

    async def test_wifi_duration_resets_after_a_change_and_timeout(self):
        self.device.details = {"network_mode": 1, "ssid": "Home", "ip": ROW["ip"],
                               "gw": "192.168.1.1", "bssid": "00:11:22:33:44:55", "rssi": 0}
        now = app.time.monotonic()
        self.device.wifi_observation = (
            ("Home", ROW["ip"], "192.168.1.1", "00:11:22:33:44:55"), now - 120, now - 60)
        self.device.details_until = now + 60

        response = await self.client.get("/network")
        station = (await response.json())["devices"][0]
        self.assertEqual(station["seconds"], 120)
        self.assertIsNone(station["rssi"])

        self.device.details = dict(self.device.details, bssid="00:11:22:33:44:66")
        self.controller.network_until = 0
        response = await self.client.get("/network")
        self.assertEqual((await response.json())["devices"][0]["seconds"], 0)

        def timed_out():
            raise Timeout("no network response")

        self.controller.network_until = 0
        with patch.object(self.device, "load_details", timed_out), self.assertLogs("twinkly", "WARNING"):
            response = await self.client.get("/network")
        self.assertEqual((await response.json())["devices"][0]["kind"], "offline")
        self.assertIsNone(self.device.wifi_observation)

    async def test_removal_is_saved_and_group_still_works(self):
        online = await self.client.post("/remove-device", json={"id": "wall"})
        self.assertEqual(await online.json(), {"ok": False})
        self.device.offline = True
        self.controller.music.add("wall")
        self.controller.patterns["wall"] = "rain"
        self.controller.sequence_devices["wall"] = 80
        with self.assertLogs("twinkly", level="INFO") as logged:
            removed = await self.client.post("/remove-device", json={"id": "wall"})
        self.assertEqual(await removed.json(), {"ok": True})
        self.assertIn("actie=verwijderen", logged.output[0])
        duplicate = await self.client.post("/remove-device", json={"id": "wall"})
        self.assertEqual(await duplicate.json(), {"ok": True})
        status = await self.get_status()
        self.assertFalse(status["devices"])
        self.assertEqual(status["groups"]["wall-group"]["members"], [])
        self.assertFalse(self.controller.music or self.controller.patterns or self.controller.sequence_devices)
        response = await self.client.post("/control", json={"group": "wall-group", "action": "off"})
        self.assertEqual(response.status, 200)
        fresh = app.Controller(self.options)
        self.addCleanup(fresh.realtime_socket.close)
        self.assertFalse(fresh.devices)
