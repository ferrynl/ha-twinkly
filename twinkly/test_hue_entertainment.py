import asyncio
import unittest
from unittest.mock import AsyncMock, Mock

from modules.hue_entertainment import EntertainmentError, HueEntertainment, RESOURCE, effect_frame

AREA = "38a6171a-af01-4eea-a634-c84b79b56a05"
PATH = f"{RESOURCE}/{AREA}"
RECORD = {"address": "192.168.1.10", "application_key": "app", "client_key": "f" * 32}


class EntertainmentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.area = {"id": AREA, "metadata": {"name": "Living room"}, "status": "inactive",
                     "channels": [{"channel_id": 3}, {"channel_id": 8}]}
        self.hue = Mock()
        self.hue.request = AsyncMock(side_effect=self.request)
        self.streamer = Mock(is_connected=True)
        self.entertainment = HueEntertainment(lambda: self.streamer)
        self.addAsyncCleanup(self.entertainment.stop)

    async def request(self, method, path, body=None):
        return [self.area] if method == "GET" else []

    async def start(self):
        await self.entertainment.start("bridge", RECORD, self.hue, AREA, "rainbow", 40)

    async def test_lists_areas_without_credentials(self):
        result = await self.entertainment.areas("bridge", RECORD, self.hue)
        self.assertEqual(result["areas"], [{"id": AREA, "name": "Living room", "busy": False}])
        self.assertNotIn("application_key", result)
        self.assertNotIn("client_key", result)

    async def test_streams_channels_then_stops(self):
        frame_sent = asyncio.Event()
        self.streamer.send_colors.side_effect = lambda commands: frame_sent.set()
        await self.start()
        await asyncio.wait_for(frame_sent.wait(), 1)
        self.assertEqual(self.entertainment.active_bridge, "bridge")
        commands, = self.streamer.send_colors.call_args.args
        self.assertEqual([command.channel_id for command in commands], [3, 8])
        self.assertNotEqual(commands[0].red, commands[1].red)
        self.streamer.connect.assert_called_once_with(RECORD["address"], "app", "f" * 32, AREA)
        await self.entertainment.stop()
        self.hue.request.assert_any_await("PUT", PATH, {"action": "start"})
        self.hue.request.assert_any_await("PUT", PATH, {"action": "stop"})
        self.hue.request.assert_awaited_with("GET", PATH)
        self.streamer.disconnect.assert_called_once()
        self.assertEqual(self.entertainment.status(), {"active": None, "error": None, "released": AREA})

    async def test_stop_acknowledged_but_area_stays_active(self):
        await self.start()
        self.area["status"] = "active"
        await self.entertainment.stop()
        self.assertEqual(self.entertainment.status(), {"active": None, "error": "stop_failed"})
        self.assertEqual(sum(call.args == ("GET", PATH) for call in self.hue.request.await_args_list), 3)

    async def test_bridge_with_existing_stream_is_left_alone(self):
        self.area["status"] = "active"
        with self.assertRaises(EntertainmentError) as raised:
            await self.start()
        self.assertEqual(raised.exception.code, "busy")
        self.hue.request.assert_awaited_once_with("GET", RESOURCE)
        self.streamer.connect.assert_not_called()

    async def test_releases_bridge_after_failed_handshake(self):
        self.streamer.connect.side_effect = OSError
        with self.assertRaises(OSError):
            await self.start()
        self.hue.request.assert_any_await("PUT", PATH, {"action": "stop"})
        self.hue.request.assert_awaited_with("GET", PATH)
        self.assertIsNone(self.entertainment.active_bridge)

    async def test_disconnected_stream_releases_bridge(self):
        await self.start()
        self.streamer.is_connected = False
        await asyncio.wait_for(asyncio.shield(self.entertainment.task), 1)
        self.hue.request.assert_any_await("PUT", PATH, {"action": "stop"})
        self.hue.request.assert_awaited_with("GET", PATH)
        self.assertEqual(self.entertainment.status(), {"active": None, "error": "stream_lost", "released": AREA})

    def test_sunset_respects_brightness(self):
        commands = effect_frame("sunset", 1, [3, 8], 40)
        self.assertTrue(all(0 < value <= 26214 for command in commands
                            for value in (command.red, command.green, command.blue)))
