from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from modules.govee_cloud import GoveeCloud, install

ID = "11:22:33:44:55:66:77:88"
SCENE_TYPE = "devices.capabilities.dynamic_scene"
SEGMENT_TYPE = "devices.capabilities.segment_color_setting"
CAPS = [
    {"type": SCENE_TYPE, "instance": "lightScene"},
    {"type": SEGMENT_TYPE, "instance": "segmentedColorRgb", "parameters": {"fields": [
        {"fieldName": "segment", "options": [{"value": 0}, {"value": 2}], "size": {"min": 1, "max": 1}},
        {"fieldName": "rgb"},
    ]}},
    {"type": SEGMENT_TYPE, "instance": "segmentedBrightness", "parameters": {"fields": [
        {"fieldName": "segment", "elementRange": {"min": 0, "max": 2}},
        {"fieldName": "brightness", "range": {"min": 0, "max": 100, "precision": 5}},
    ]}},
]


@asynccontextmanager
async def can_control(device):
    yield


class GoveeCloudTests(unittest.IsolatedAsyncioTestCase):
    async def client(self, key=None, cache_path=None):
        app = web.Application()
        install(app, key, can_control, cache_path)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_opt_in_and_commands_use_model_data_from_account(self):
        client = await self.client("test-credential")
        calls = []

        async def request(_, method, path, payload=None):
            calls.append((method, path, payload))
            if path == "/user/devices":
                return {"data": [
                    {"device": ID, "sku": "H605C", "deviceName": "Woonkamer",
                     "type": "devices.types.light", "capabilities": CAPS},
                    {"device": "socket", "sku": "K567", "type": "devices.types.socket"},
                ]}
            if path == "/device/scenes":
                return {"payload": {"capabilities": [{"type": SCENE_TYPE, "instance": "lightScene",
                        "parameters": {"options": [{"name": "Sunrise", "value": {"id": 85, "paramId": 42}}]}}]}}
            return {}

        with patch.object(GoveeCloud, "request", autospec=True, side_effect=request):
            root = "/providers/govee/cloud"
            settings = await (await client.get(root)).json()
            self.assertEqual(settings, {"configured": True, "devices": []})
            self.assertEqual(calls, [])
            devices = await (await client.post(root + "/devices", json={})).json()
            self.assertEqual(devices, {"devices": [{"id": ID, "name": "Woonkamer", "sku": "H605C"}]})
            detail = await (await client.post(root + "/details", json={"device": ID})).json()
            self.assertEqual(detail["segments"]["color"]["indices"], [0, 2])
            self.assertEqual(detail["segments"]["brightness"]["indices"], [0, 1, 2])
            scene, = detail["scenes"]
            self.assertEqual(scene["name"], "Sunrise")
            response = await client.post(root + "/apply", json={"device": ID, "action": "color",
                                         "segments": [2], "value": [255, 127, 5], "sku": "WRONG"})
            self.assertEqual(await response.json(), {"accepted": True})
            self.assertEqual(calls[-1], ("POST", "/device/control", {"device": ID, "sku": "H605C",
                             "capability": {"type": SEGMENT_TYPE, "instance": "segmentedColorRgb",
                                            "value": {"segment": [2], "rgb": 0xff7f05}}}))
            response = await client.post(root + "/apply", json={"device": ID, "action": "scene", "scene": scene["id"]})
            self.assertEqual(response.status, 200)
            self.assertEqual(calls[-1][2]["capability"]["value"], {"id": 85, "paramId": 42})
            self.assertEqual([path for _, path, _ in calls],
                             ["/user/devices", "/device/scenes", "/device/control", "/device/control"])

    async def test_invalid_segments_and_values_do_not_send_commands(self):
        cloud = GoveeCloud("test-credential")
        device = {"id": ID, "sku": "H605C", "caps": CAPS}
        for data in ({"action": "color", "segments": [1], "value": [0, 0, 0]},
                     {"action": "color", "segments": [0, 2], "value": [0, 0, 0]},
                     {"action": "brightness", "segments": [1, 1], "value": 50},
                     {"action": "brightness", "segments": [True], "value": 50},
                     {"action": "brightness", "segments": [1], "value": 51}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                await cloud.capability(device, data)
        capability = await cloud.capability(device, {"action": "brightness", "segments": [1, 2], "value": 0})
        self.assertEqual(capability["value"], {"segment": [1, 2], "brightness": 0})

    async def test_disabled_returns_no_configured_key(self):
        client = await self.client()
        root = "/providers/govee/cloud"
        self.assertEqual(await (await client.get(root)).json(), {"configured": False, "devices": []})
        response = await client.post(root + "/devices", json={})
        self.assertEqual(response.status, 409)
        self.assertEqual(await response.json(), {"error": "disabled"})

    async def test_synced_devices_persist_and_are_scoped_to_the_key(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "govee.json"
            client = await self.client("test-credential", path)
            root = "/providers/govee/cloud"
            payload = {"data": [{"device": ID, "sku": "H605C", "type": "devices.types.light"}]}
            with patch.object(GoveeCloud, "request", return_value=payload) as request:
                await client.post(root + "/devices", json={})
                reopened = await self.client("test-credential", path)
                self.assertEqual((await (await reopened.get(root)).json())["devices"][0]["id"], ID)
                other_account = await self.client("different-credential", path)
                self.assertEqual((await (await other_account.get(root)).json())["devices"], [])
                request.assert_awaited_once()
