"""Verify offline status, app logs, recovery and removing saved devices."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import call, patch

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

    async def test_offline_background_checks_share_backoff_and_log_once(self):
        calls = []

        def read_mode():
            calls.append("read_mode")
            raise ConnectionError("No route to host")

        def load_details():
            calls.append("load_details")
            raise Timeout("connection timed out")

        with self.assertLogs("twinkly", level="WARNING") as logged:
            self.assertFalse(await self.device.run(read_mode, automatic=True))
        self.assertEqual(len(logged.output), 1)
        with self.assertNoLogs("twinkly", level="WARNING"):
            self.assertFalse(await self.device.run(load_details, automatic=True))
            self.assertEqual(calls, ["read_mode"])
            for _ in range(3):
                self.device.retry = 0
                self.device.last_warning_at -= 120
                self.assertFalse(await self.device.run(load_details, automatic=True))
        self.assertEqual(calls, ["read_mode", "load_details", "load_details", "load_details"])
        self.assertTrue((await self.get_status())["devices"][0]["offline"])

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
        # Use an exact second so floating-point truncation cannot affect the assertion.
        now = int(app.time.monotonic())
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

    async def test_native_group_is_one_control_target_and_respects_local_alias(self):
        peer_row = dict(ROW, id="peer", name="Rand", ip="192.168.1.212")
        peer = app.Device(peer_row, self.controller.limit, self.controller.realtime_socket)
        self.addCleanup(peer.client.session.close)
        self.controller.devices["peer"] = peer
        with patch.object(self.device,"api",return_value={
            "group": {"mode": "master", "master_id": "wall-sync", "name": "Muur"}
        }), patch.object(peer,"api",side_effect=[
            {"group": {"mode": "slave"}},
            {"sync": {"mode": "slave", "master_id": "wall-sync"}},
        ]):
            self.device.load_native_group()
            peer.load_native_group()
        self.device.details_until = peer.details_until = app.time.monotonic() + 60

        response = await self.client.get("/network")
        native = (await response.json())["groups"]["native:wall-sync"]
        self.assertEqual(native, {"name": "Muur", "members": ["wall", "peer"], "mode": "sync"})
        with patch.object(self.device,"command") as first, patch.object(peer,"command") as second:
            response = await self.client.post("/control", json={"group": "native:wall-sync", "action": "off"})
            self.assertEqual(response.status, 200)
            first.assert_called_once_with("off", None)
            second.assert_called_once_with("off", None)

        response = await self.client.post("/network/groups/name", json={
            "id": "native:wall-sync", "name": "  Kerstmuur  ",
        })
        self.assertEqual(await response.json(), {"name": "Kerstmuur"})
        response = await self.client.get("/network")
        self.assertEqual((await response.json())["groups"]["native:wall-sync"]["name"], "Kerstmuur")
        status = await self.get_status()
        self.assertEqual(status["display_groups"]["native:wall-sync"]["name"], "Kerstmuur")
        self.assertEqual(status["display_groups"]["native:wall-sync"]["members"], ["wall", "peer"])
        self.assertNotIn("native:wall-sync", status["groups"])
        fresh = app.Controller(self.options)
        self.addCleanup(fresh.realtime_socket.close)
        self.assertEqual(fresh.native_group_names["native:wall-sync"], "Kerstmuur")
        response = await self.client.post("/network/groups/name", json={
            "id": "native:missing", "name": "Onbekend",
        })
        self.assertEqual(response.status, 404)

        self.controller.groups["custom-wall"] = {"name": "Eigen Muur", "members": ["peer","wall"]}
        response = await self.client.get("/network")
        groups = (await response.json())["groups"]
        self.assertNotIn("native:wall-sync", groups)
        self.assertEqual(groups["custom-wall"]["name"], "Eigen Muur")

    async def test_group_role_without_master_id_is_visible_without_guessing_members(self):
        with patch.object(self.device,"api",side_effect=[
            {"group": {"mode": "slave"}},
            {"sync": {"mode": "slave", "slave_id": "one"}},
        ]):
            self.device.load_native_group()
        self.device.details_until = app.time.monotonic() + 60
        response = await self.client.get("/network")
        payload = await response.json()
        self.assertEqual(payload["devices"][0]["group_role"], "slave")
        self.assertFalse(any(key.startswith("native:") for key in payload["groups"]))

    async def test_group_uid_with_wall_layout_uses_led_order_and_common_name(self):
        uid = "c925f829-a571-40d7-9761-f6b9161337da"
        master = app.Device(dict(ROW, id="master", name="Muur 1", ip="192.168.1.150"),
                            self.controller.limit, self.controller.realtime_socket)
        fourth = app.Device(dict(ROW, id="fourth", name="Muur 4", ip="192.168.1.188"),
                            self.controller.limit, self.controller.realtime_socket)
        for device in (master, fourth):
            self.addCleanup(device.client.session.close)
            self.controller.devices[device.row["id"]] = device
        for device, fields in (
            (self.device, {"mode": "slave", "offset": 420}),
            (master, {"mode": "master"}),
            (fourth, {"mode": "slave", "offset": 630}),
        ):
            with patch.object(device, "api", return_value={
                "group": dict(fields, uid=uid, size=840, time_sync=False, sync_on_time=False)
            }) as api:
                device.load_native_group()
            self.assertEqual(api.call_args_list, [call("summary"), call("led/movie/config")])
            device.details_until = app.time.monotonic() + 60

        response = await self.client.get("/network")
        self.assertEqual(response.status, 200)
        groups = (await response.json())["groups"]
        self.assertEqual(groups["native:" + uid], {
            "name": "Muur", "members": ["master", "wall", "fourth"], "layout_size": 840, "mode": "join",
        })

    def join_wall(self, *, master_id=""):
        for index, key in enumerate(("master", "second", "wall", "fourth")):
            if key not in self.controller.devices:
                row = dict(ROW, id=key, name=f"Muur {index + 1}", ip=f"192.168.1.{150 + index}")
                device = app.Device(row, self.controller.limit, self.controller.realtime_socket)
                self.addCleanup(device.client.session.close)
                self.controller.devices[key] = device
            if index:
                device = self.controller.devices[key]
                with patch.object(device, "api", side_effect=[
                    {"group": {"mode": "slave", "uid": "wall-uid", "name": "Muur2026"}},
                    {"sync": {"mode": "slave", "master_id": master_id, "offset": 210 * index, "size": 840}},
                ]):
                    device.load_native_group()
        return self.controller.devices["master"]

    async def test_missing_master_recovers_only_with_native_identity(self):
        master = self.join_wall(master_id="MASTER-UUID")
        group = "native:wall-uid"
        self.assertEqual(self.controller.native_groups()[group]["members"], ["second", "wall", "fourth"])
        master.remember_native_identity({"uuid": "master-uuid"})
        self.assertEqual(self.controller.native_groups()[group]["members"], ["master", "second", "wall", "fourth"])
        master.layout = {"points": [[i, i, i, 0] for i in range(840)]}
        master.layout_until = float("inf")
        response = await self.client.get("/group-layout", params={"id": group})
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["leds"], 840)

    async def test_spatial_tests_and_layout_explain_missing_master(self):
        self.join_wall()
        group = "native:wall-uid"
        self.assertEqual(self.controller.native_groups()[group]["missing_master"], group)
        with self.assertLogs("twinkly", "WARNING") as logged:
            response = await self.client.get("/group-layout", params={"id": group})
            self.assertEqual(response.status, 409)
            self.assertIn("explicitly associate", (await response.json())["error"])
            for test in ("rainbow", "horizontal", "vertical"):
                response = await self.client.post("/physical-test", json={"group": group, "test": test})
                self.assertEqual(response.status, 409)
                self.assertIn("exactly one native master", (await response.json())["error"])
                self.assertIn(f"operation={test}", logged.output[-1])
        self.assertFalse(self.controller.physical_tests)
        response = await self.client.post("/physical-test", json={"group": group, "test": "identify"})
        self.assertEqual(response.status, 200)
        self.assertEqual(set(self.controller.physical_tests), {"second", "wall", "fourth"})

    async def test_standalone_controller_recovers_by_shared_layout_and_leading_gap(self):
        master = self.join_wall()
        group = "native:wall-uid"
        for index, key in enumerate(("master", "second", "wall", "fourth")):
            device = self.controller.devices[key]
            device.native_group_until = 0
            summary = {"layout": {"uuid": "SHARED-LAYOUT"}}
            if key == "master":
                summary["group"] = {"mode": "none"}
            else:
                summary["group"] = dict(mode="slave", uid="wall-uid", size=840, offset=index * 210)
            with patch.object(device, "api", side_effect=[summary, {"sync": {"mode": summary["group"]["mode"]}}]):
                device.load_native_group()
            device.layout = {"uuid": "shared-layout", "points": [[i, i, index, 0] for i in range(210)]}
            device.layout_until = float("inf")

        self.assertEqual(self.controller.native_groups()[group]["members"], ["master", "second", "wall", "fourth"])
        response = await self.client.get("/group-layout", params={"id": group})
        self.assertEqual(response.status, 200)
        layout = await response.json()
        self.assertEqual(layout["leds"], 840)
        self.assertEqual([entry["points"][0][1] for entry in layout["members"]], [0, 1/3, 2/3, 1])
        response = await self.client.post("/physical-test", json={"group": group, "test": "rainbow"})
        self.assertEqual(response.status, 200)

        self.device.layout["uuid"] = "different"
        response = await self.client.get("/group-layout", params={"id": group})
        self.assertEqual(response.status, 409)
        self.assertIn("matching physical mapping IDs", (await response.json())["error"])

        duplicate = app.Device(dict(master.row, id="duplicate"), self.controller.limit, self.controller.realtime_socket)
        self.addCleanup(duplicate.client.session.close)
        self.controller.devices["duplicate"] = duplicate
        duplicate.native_layout_id = master.native_layout_id
        duplicate.native_standalone = True
        self.assertEqual(self.controller.native_groups()[group]["missing_master"], group)
        duplicate.native_layout_id = "different"
        self.device.native_group["offset"] = 421
        self.assertEqual(self.controller.native_groups()[group]["missing_master"], group)

    async def test_manual_master_validates_offsets_and_map_and_can_be_removed(self):
        master = self.join_wall()
        group = "native:wall-uid"
        association = {"group": group, "device": "master"}
        self.device.native_group["offset"] = 421
        response = await self.client.post("/network/groups/master", json=association)
        self.assertEqual(response.status, 409)
        self.assertIn("Muur 3 is 421 (expected 420)", (await response.json())["error"])
        self.device.native_group["offset"] = 420
        with patch.object(master, "api", return_value={"coordinates": []}):
            response = await self.client.post("/network/groups/master", json=association)
        self.assertEqual(response.status, 409)
        self.assertIn("complete physical map for all 840 LEDs", (await response.json())["error"])
        self.assertNotIn("native_master_for", master.row)
        with patch.object(master, "api", return_value={"coordinates": [{"x": i, "y": i} for i in range(840)]}):
            response = await self.client.post("/network/groups/master", json=association)
        self.assertEqual(response.status, 200)
        self.assertEqual(self.controller.native_groups()[group]["manual_master"], association)
        self.assertEqual(next(row for row in json.loads(app.DATA.read_text()) if row["id"] == "master")["native_master_for"], "wall-uid")
        response = await self.client.post("/network/groups/master", json=dict(association, remove=True))
        self.assertEqual(response.status, 200)
        self.assertEqual(self.controller.native_groups()[group]["missing_master"], group)

    async def test_incomplete_offsets_are_reported_even_with_a_native_master(self):
        master = self.join_wall(master_id="known-master")
        master.remember_native_identity({"uuid": "known-master"})
        self.device.native_group["offset"] = None
        response = await self.client.post("/physical-test", json={"group": "native:wall-uid", "test": "vertical"})
        self.assertEqual(response.status, 409)
        self.assertIn("Join offset is missing for Muur 3", (await response.json())["error"])

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
