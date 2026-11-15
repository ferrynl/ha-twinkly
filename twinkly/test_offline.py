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
