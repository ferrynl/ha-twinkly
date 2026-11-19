import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from modules.lighting import light_key
from modules.provider_routes import install
from modules.provider_store import ProviderStore


class LightingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = ProviderStore(temp.name)
        self.store.save({
            "version": 1,
            "hue": {"bridge": {"address": "192.168.1.2", "application_key": "private_key",
                               "certificate_sha256": "ab" * 32}},
            "govee": {"strip": {"address": "192.168.1.3"}, "silent": {"address": "192.168.1.4"}},
        })
        self.controller = SimpleNamespace(
            devices={"tree": SimpleNamespace(row={"name": "Tree"}, offline=False, mode="color",
                                             last_brightness=70, last_color=[255, 10, 0])},
            apply_control=AsyncMock(return_value={"failed": []}),
        )
        self.hue_id = "f735a5a7-819a-4bbf-89d4-e48b8c11db8c"
        self.twinkly = light_key("twinkly", "tree")
        self.hue = light_key("hue", "bridge", self.hue_id)
        self.govee = light_key("govee", "strip", "strip")
        self.silent = light_key("govee", "silent", "silent")
        for name, value in {
            "Hue.profiles": [{"id": self.hue_id, "name": "White Hue",
                              "capabilities": {"power": True, "rgb": False}, "state": {"on": True}}],
            "govee_statuses": {"192.168.1.3": {"onOff": 1, "color": {"r": 255, "g": 1, "b": 2}}},
            "Hue.control": None,
            "Govee.color": None,
        }.items():
            patcher = patch("modules.provider_routes." + name, new=AsyncMock(return_value=value))
            setattr(self, name.split(".")[-1], patcher.start())
            self.addCleanup(patcher.stop)
        app = web.Application()
        install(app, self.store, self.controller)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    async def test_normalized_inventory_and_redaction(self):
        response = await self.client.get("/lighting")
        self.assertNotIn("private_key", await response.text())
        self.assertNotIn("certificate_sha256", await response.text())
        data = await response.json()
        self.assertEqual(data["connections"]["hue"][0]["status"], "online")
        lights = {light["id"]: light for light in data["lights"]}
        self.assertEqual(lights[self.twinkly]["state"]["brightness"], 70)
        self.assertFalse(lights[self.hue]["capabilities"]["rgb"])
        self.assertTrue(lights[self.govee]["capabilities"]["rgb"])
        self.assertFalse(lights[self.govee]["verified"])
        self.assertEqual(lights[self.govee]["status"], "reported")
        self.assertEqual(lights[self.silent]["status"], "unknown")
        self.assertFalse(lights[self.silent]["capabilities"]["power"])

    async def test_cross_brand_group_gates_color_and_persists(self):
        response = await self.client.post("/lighting/groups", json={
            "name": "Wall", "members": [self.twinkly, self.hue, self.govee, self.silent, self.hue],
        })
        self.assertEqual(response.status, 200)
        group = (await response.json())["id"]
        self.assertEqual(ProviderStore(self.store.path.parent).load_groups()[group]["members"],
                         [self.twinkly, self.hue, self.govee, self.silent])
        response = await self.client.post("/lighting/control", json={
            "group": group, "action": "color", "value": [255, 10, 0],
        })
        self.assertEqual((await response.json())["results"], {
            self.twinkly: "accepted", self.hue: "skipped", self.govee: "unconfirmed", self.silent: "skipped",
        })
        self.controller.apply_control.assert_awaited_once_with(
            {"id": "tree", "action": "color", "value": "#ff0a00"})
        self.control.assert_not_awaited()
        self.color.assert_awaited_once_with([255, 10, 0])

        self.profiles.side_effect = TimeoutError
        response = await self.client.post("/lighting/groups", json={
            "id": group, "name": "Wall 2", "members": [self.twinkly, self.hue],
        })
        self.assertEqual(response.status, 200)
        response = await self.client.post("/lighting/control", json={"group": group, "action": "power", "value": False})
        self.assertEqual((await response.json())["results"], {self.twinkly: "accepted", self.hue: "skipped"})
        response = await self.client.post("/lighting/groups", json={"id": group, "delete": True})
        self.assertEqual(response.status, 200)
        self.assertEqual(self.store.load_groups(), {})

    async def test_hue_power_and_invalid_payloads(self):
        response = await self.client.post("/lighting/control", json={"id": self.hue, "action": "power", "value": True})
        self.assertEqual((await response.json())["results"], {self.hue: "accepted"})
        self.control.assert_awaited_once_with(self.hue_id, on=True)
        for payload in ([],
                        {"id": self.hue, "action": "brightness", "value": True},
                        {"id": self.hue, "action": "power", "value": 1}):
            response = await self.client.post("/lighting/control", json=payload)
            self.assertEqual(response.status, 400)
