import unittest
import tempfile
from unittest.mock import AsyncMock, patch
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
