import asyncio
import json
import ssl
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from modules.common import RateGate, lan_ip, rgb, brightness
from modules.hue import Hue, xy_color
from modules.govee import Govee, packet

RID = "12345678-1234-1234-1234-123456789abc"

class Boundaries(unittest.TestCase):
    def test_private_networks(self):
        for addr in ("10.0.0.1","172.16.0.1","172.31.255.254","192.168.0.1"):
            with self.subTest(addr=addr): self.assertEqual(lan_ip(addr),addr)
    def test_reject_non_lan(self):
        for addr in ("0.0.0.0","255.255.255.255","224.0.0.1","172.15.1.1","172.32.1.1","::1","192.168.1.1:80","169.254.169.254"):
            with self.subTest(addr=addr), self.assertRaises(ValueError): lan_ip(addr)
    def test_rgb_boundaries(self):
        for value in ([0,0,0],[255,255,255],[0,128,255]):
            self.assertEqual(rgb(value),value)
    def test_rgb_types(self):
        for value in (None,"123",[1.0,2,3],[-1,0,0],[1,2,3,4]):
            with self.subTest(value=value), self.assertRaises(ValueError): rgb(value)
    def test_level(self):
        for value in (1,100): self.assertEqual(brightness(value),value)
        for value in (None,"50",50.0,-1,False):
            with self.subTest(value=value), self.assertRaises(ValueError): brightness(value)
    def test_xy_primaries(self):
        for value in ([255,0,0],[0,255,0],[0,0,255],[255,255,255]):
            c=xy_color(value)
            self.assertGreaterEqual(c["x"],0)
            self.assertGreaterEqual(c["y"],0)
            self.assertLessEqual(c["x"]+c["y"],1)
    def test_black_rejected(self):
        with self.assertRaises(ValueError): xy_color([0,0,0])

class ProviderContract(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.hue=Hue("192.168.1.2","test-key",ssl.create_default_context())
        self.hue.request=AsyncMock(return_value=[])
        self.govee=Govee("192.168.1.3")
        self.govee.send=AsyncMock()
    async def test_hue_list(self):
        await self.hue.lights()
        self.hue.request.assert_awaited_once_with("GET","light")
    async def test_hue_off(self):
        await self.hue.control(RID,on=False)
        self.hue.request.assert_awaited_once_with("PUT","light/"+RID,{"on":{"on":False}})
    async def test_hue_color(self):
        await self.hue.control(RID,color=[0,255,0])
        self.hue.request.assert_awaited_once_with("PUT","light/"+RID,{"color":{"xy":xy_color([0,255,0])}})
    async def test_hue_invalid_id(self):
        for value in ("../light","", "https://example.com"):
            with self.assertRaises(ValueError): await self.hue.control(value,on=True)
        self.hue.request.assert_not_awaited()
    async def test_hue_invalid_commands(self):
        for kwargs in ({},{"on":1},{"level":101},{"color":[0,0,0]}):
            with self.assertRaises(ValueError): await self.hue.control(RID,**kwargs)
        self.hue.request.assert_not_awaited()
    async def test_govee_power(self):
        await self.govee.power(True)
        await self.govee.power(False)
        self.assertEqual([c.args for c in self.govee.send.await_args_list],[("turn",{"value":1}),("turn",{"value":0})])
    async def test_govee_dim(self):
        await self.govee.dim(42)
        self.govee.send.assert_awaited_once_with("brightness",{"value":42})
    async def test_govee_invalid(self):
        for fn,arg in ((self.govee.power,1),(self.govee.dim,0),(self.govee.color,[1,2,999])):
            with self.assertRaises(ValueError): await fn(arg)
        self.govee.send.assert_not_awaited()
    async def test_failure_isolation(self):
        self.hue.request.side_effect=TimeoutError()
        result=await asyncio.gather(self.hue.lights(),self.govee.power(True),return_exceptions=True)
        self.assertIsInstance(result[0],TimeoutError)
        self.govee.send.assert_awaited_once()

class RateGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_serialization(self):
        gate=RateGate(0)
        active=peak=0
        async def action():
            nonlocal active,peak
            active+=1
            peak=max(peak,active)
            await asyncio.sleep(0)
            active-=1
        await asyncio.gather(*(gate.run(action) for _ in range(20)))
        self.assertEqual(peak,1)
    async def test_failure_releases_gate(self):
        gate=RateGate(0)
        with self.assertRaises(TimeoutError):
            await gate.run(AsyncMock(side_effect=TimeoutError()))
        self.assertEqual(await gate.run(AsyncMock(return_value=42)),42)
    async def test_interval(self):
        gate=RateGate(.02)
        loop=asyncio.get_running_loop()
        stamps=[]
        async def send(): stamps.append(loop.time())
        await asyncio.gather(gate.run(send),gate.run(send))
        self.assertGreaterEqual(stamps[1]-stamps[0],.019)
    async def test_cancel_releases_gate(self):
        gate=RateGate(0)
        started=asyncio.Event()
        async def blocked():
            started.set()
            await asyncio.Event().wait()
        task=asyncio.create_task(gate.run(blocked))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(await asyncio.wait_for(gate.run(AsyncMock(return_value=1)),1),1)
