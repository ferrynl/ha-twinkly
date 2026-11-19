import unittest
import tempfile
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
