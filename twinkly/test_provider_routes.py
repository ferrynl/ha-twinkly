import base64
from io import BytesIO
import unittest
import tempfile
from unittest.mock import AsyncMock, patch
from PIL import Image
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from modules.provider_routes import install
from modules.provider_store import ProviderStore

class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store=ProviderStore(self.temp.name)
        app=web.Application()
        install(app,self.store)
        self.client=TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
    async def test_configured(self):
        r=await self.client.get("/providers/configured")
        self.assertEqual(await r.json(),{"hue":{},"govee":{}})
    async def test_unknown(self):
        r=await self.client.post("/providers/other/discover",json={})
        self.assertEqual(r.status,404)
    async def test_empty_inventory(self):
        r=await self.client.get("/providers/hue/inventory")
        self.assertEqual(await r.json(),{"devices":[]})
    async def test_secret_redaction(self):
        self.store.save({"version":1,"govee":{},"hue":{"a":{"address":"192.168.1.2","application_key":"abcdefghij","certificate_sha256":"ab"*32}}})
        r=await self.client.get("/providers/configured")
        self.assertNotIn("abcdefghij",await r.text())
    async def test_govee_inventory(self):
        self.store.save({"version":1,"hue":{},"govee":{"a":{"address":"192.168.1.2"}}})
        r=await self.client.get("/providers/govee/inventory")
        self.assertEqual((await r.json())["devices"][0]["status"],"unknown")

    async def test_connect_govee(self):
        r=await self.client.post("/providers/govee/connect",json={"id":"test","address":"192.168.1.4"})
        self.assertEqual(r.status,200)
        self.assertEqual(self.store.load()["govee"]["test"]["address"],"192.168.1.4")
    async def test_connect_public_ip_rejected(self):
        r=await self.client.post("/providers/govee/connect",json={"id":"test","address":"8.8.8.8"})
        self.assertEqual(r.status,400)
        self.assertEqual(self.store.load()["govee"],{})
    async def test_hue_pairing_button(self):
        with patch("modules.provider_routes.pair",new=AsyncMock(side_effect=PermissionError)):
            r=await self.client.post("/providers/hue/connect",json={"id":"bridge","address":"192.168.1.4","certificate_sha256":"ab"*32})
        self.assertEqual(r.status,409)
        self.assertEqual(self.store.load()["hue"],{})
    async def test_hue_pairing_redacts_credentials(self):
        with patch("modules.provider_routes.pair",new=AsyncMock(return_value={"application_key":"abcdefghij","client_key":None})):
            r=await self.client.post("/providers/hue/connect",json={"id":"bridge","address":"192.168.1.4","certificate_sha256":"ab"*32})
        self.assertEqual(r.status,200)
        self.assertNotIn("abcdefghij",await r.text())
        self.assertEqual(self.store.load()["hue"]["bridge"]["application_key"],"abcdefghij")
    async def test_govee_control_unconfirmed(self):
        self.store.save({"version":1,"hue":{},"govee":{"test":{"address":"192.168.1.4"}}})
        with patch("modules.provider_routes.Govee.power",new=AsyncMock()) as send:
            r=await self.client.post("/providers/govee/control",json={"id":"test","action":"power","value":True})
            send.assert_awaited_once_with(True)
        self.assertEqual(await r.json(),{"ok":True,"confirmed":False})
    async def test_unknown_device_control(self):
        r=await self.client.post("/providers/govee/control",json={"id":"missing","action":"power","value":True})
        self.assertEqual(r.status,400)
    async def test_unknown_action(self):
        self.store.save({"version":1,"hue":{},"govee":{"test":{"address":"192.168.1.4"}}})
        r=await self.client.post("/providers/govee/control",json={"id":"test","action":"unknown","value":True})
        self.assertEqual(r.status,400)
    async def test_invalid_brightness(self):
        self.store.save({"version":1,"hue":{},"govee":{"test":{"address":"192.168.1.4"}}})
        r=await self.client.post("/providers/govee/control",json={"id":"test","action":"brightness","value":101})
        self.assertEqual(r.status,400)

    async def test_certificate_inspection_is_unverified(self):
        with patch("modules.provider_routes.inspect_certificate",new=AsyncMock(return_value="ab"*32)) as inspect:
            r=await self.client.post("/providers/hue/certificate",json={"address":"192.168.1.4"})
            inspect.assert_awaited_once_with("192.168.1.4")
        self.assertEqual(await r.json(),{"certificate_sha256":"ab"*32,"verified":False})
        self.assertEqual(self.store.load()["hue"],{})
    async def test_certificate_public_address_rejected(self):
        with patch("modules.provider_routes.inspect_certificate",new=AsyncMock()) as inspect:
            r=await self.client.post("/providers/hue/certificate",json={"address":"8.8.8.8"})
            inspect.assert_not_awaited()
        self.assertEqual(r.status,400)

    async def test_hue_collections_report_rooms_zones_and_scenes_per_bridge(self):
        self.store.save({"version": 1, "govee": {}, "hue": {
            name: {"address": address, "application_key": "abcdefghij", "certificate_sha256": "ab" * 32}
            for name, address in [("first", "192.168.1.2"), ("offline", "192.168.1.3")]
        }})
        resources = {
            "room": [{"id": "room", "metadata": {"name": "Woonkamer"},
                      "services": [{"rtype": "grouped_light", "rid": "room-control"}],
                      "children": [{"rtype": "device", "rid": "lamp-device"}]}],
            "device": [{"id": "lamp-device", "services": [{"rtype": "light", "rid": "lamp"}]}],
            "zone": [{"id": "zone", "metadata": {"name": "Kersthoek"}}],
            "grouped_light": [{"id": "room-control", "on": {"on": True}, "dimming": {"brightness": 42}}],
            "scene": [{"id": "scene", "metadata": {"name": "Avondlicht"},
                       "group": {"rtype": "zone", "rid": "zone"}}],
        }

        async def request(client, method, resource):
            if client.address == "192.168.1.3":
                raise TimeoutError()
            self.assertEqual(method, "GET")
            return resources[resource]

        with patch("modules.hue.Hue.request", autospec=True, side_effect=request):
            response = await self.client.get("/providers/hue/collections")
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["bridges"], [
            {"id": "first", "status": "online", "address": "192.168.1.2", "collections": [
                {"id": "room", "kind": "room", "members": ["lamp"], "name": "Woonkamer", "grouped_light": "room-control",
                 "on": True, "brightness": 42, "scenes": []},
                {"id": "zone", "kind": "zone", "members": [], "name": "Kersthoek", "grouped_light": None,
                 "on": None, "brightness": None, "scenes": [{"id": "scene", "name": "Avondlicht"}]},
            ]},
            {"id": "offline", "status": "unavailable", "address": "192.168.1.3", "collections": []},
        ])

    async def test_hue_scene_previews_use_palette_white_temperature_and_brightness(self):
        self.store.save({"version": 1, "govee": {}, "hue": {
            "bridge": {"address": "192.168.1.2", "application_key": "abcdefghij", "certificate_sha256": "ab" * 32},
        }})
        group = {"rtype": "room", "rid": "room"}
        warm = {"color_temperature": {"mirek": 500}}
        cool = {"color_temperature": {"mirek": 153}}
        dim = {"dimming": {"brightness": 4}}
        off = {"on": {"on": False}, **cool}
        resources = {
            "room": [{"id": "room"}],
            "zone": [],
            "grouped_light": [],
            "scene": [
                {"id": "palette", "group": group, "palette": {"color_temperature": [cool]},
                 "actions": [{"action": warm}]},
                {"id": "warm", "group": group, "actions": [{"action": off}, {"action": warm}]},
                {"id": "dim", "group": group, "actions": [{"action": dim}]},
                {"id": "dim-palette", "group": group, "palette": {"dimming": [dim["dimming"]]}},
                {"id": "off", "group": group, "actions": [{"action": off}]},
                {"id": "unknown", "group": group},
            ],
        }

        async def request(client, method, resource):
            return resources[resource]

        with patch("modules.hue.Hue.request", autospec=True, side_effect=request):
            response = await self.client.get("/providers/hue/collections")
        self.assertEqual(response.status, 200)
        scenes = (await response.json())["bridges"][0]["collections"][0]["scenes"]
        self.assertEqual({scene["id"]: scene.get("palette") for scene in scenes}, {
            "palette": [[225, 238, 255]],
            "warm": [[255, 172, 96]],
            "dim": [[96, 92, 85]],
            "dim-palette": [[96, 92, 85]],
            "off": [[38, 43, 58]],
            "unknown": None,
        })

    async def test_hue_collection_actions_use_native_resource_commands(self):
        self.store.save({"version": 1, "govee": {}, "hue": {
            "bridge": {"address": "192.168.1.2", "application_key": "abcdefghij", "certificate_sha256": "ab" * 32},
        }})
        resource = "00000000-0000-4000-8000-000000000001"
        cases = [
            ("power", False, "grouped_light", {"on": {"on": False}}),
            ("brightness", 42, "grouped_light", {"dimming": {"brightness": 42}}),
            ("recall", None, "scene", {"recall": {"action": "active"}}),
        ]
        with patch("modules.hue.Hue.request", new=AsyncMock()) as send:
            for action, value, kind, payload in cases:
                response = await self.client.post("/providers/hue/collections/control", json={
                    "bridge": "bridge", "id": resource, "action": action, "value": value,
                })
                self.assertEqual(response.status, 200)
                send.assert_awaited_once_with("PUT", f"{kind}/{resource}", payload)
                send.reset_mock()
            response = await self.client.post("/providers/hue/collections/control", json={
                "bridge": "bridge", "id": "../resource", "action": "recall",
            })
            self.assertEqual(response.status, 400)
            send.assert_not_awaited()

    async def test_scene_image_is_stored_by_bridge_and_can_be_removed(self):
        self.store.save({"version": 1, "govee": {}, "hue": {
            name: {"address": address, "application_key": "abcdefghij", "certificate_sha256": "ab" * 32}
            for name, address in [("first", "192.168.1.2"), ("second", "192.168.1.3")]
        }})
        scene = "00000000-0000-4000-8000-000000000001"
        path = f"/providers/hue/scene-image/first/{scene}"
        image = BytesIO()
        Image.new("RGB", (16, 12), "red").save(image, "JPEG")
        encoded = base64.b64encode(image.getvalue()).decode("ascii")
        response = await self.client.post(path, json={"image": "invalid"})
        self.assertEqual(response.status, 400)
        response = await self.client.post(path, json={"image": encoded})
        self.assertEqual(response.status, 200)
        response = await self.client.get(path)
        self.assertEqual(response.content_type, "image/jpeg")
        with Image.open(BytesIO(await response.read())) as decoded:
            self.assertEqual(decoded.size, (16, 12))
        response = await self.client.get(f"/providers/hue/scene-image/second/{scene}")
        self.assertEqual(response.status, 404)
        response = await self.client.post(path, json={"image": None})
        self.assertEqual(response.status, 200)
        response = await self.client.get(path)
        self.assertEqual(response.status, 404)

    async def test_product_photo_validates_alpha_and_is_shared_by_model(self):
        path = "/providers/hue/product-image/lst002"
        for mode, color, expected in (("RGB", "red", 400), ("RGBA", (0, 0, 0, 0), 200)):
            image = Image.new(mode, (16, 12), color)
            image.putpixel((2, 2), (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0))
            buffer = BytesIO()
            image.save(buffer, "PNG")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            response = await self.client.post(path, json={"image": encoded})
            self.assertEqual(response.status, expected)
        response = await self.client.get("/providers/hue/product-image/LST002")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        with Image.open(BytesIO(await response.read())) as saved:
            self.assertEqual(saved.mode, "RGBA")
            self.assertEqual(saved.getchannel("A").getextrema(), (0, 255))

        self.store.save({"version": 1, "govee": {}, "hue": {"bridge": {
            "address": "192.168.1.2", "application_key": "abcdefghij", "certificate_sha256": "ab" * 32,
        }}})
        with patch("modules.provider_routes.Hue.profiles", new=AsyncMock(return_value=[{"model": "LST002"}])):
            response = await self.client.get("/providers/hue/inventory")
            self.assertTrue((await response.json())["devices"][0]["lights"][0]["has_product_image"])
        response = await self.client.post(path, json={"image": None})
        self.assertEqual(response.status, 200)
        fallback = await self.client.get(path)
        self.assertEqual(fallback.status, 200)
        self.assertEqual(fallback.content_type, "image/png")
        self.assertEqual((await self.client.get("/providers/hue/product-image/UNKNOWN-000")).status, 404)
