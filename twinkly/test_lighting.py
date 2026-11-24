import asyncio
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from modules.lighting import light_key
from modules.lighting_projects import Playback, show_settings, start_show_music
from modules.provider_routes import install
from modules.provider_store import ProviderStore
from modules.hue_entertainment import HueEntertainment, RESOURCE

AREA = "38a6171a-af01-4eea-a634-c84b79b56a05"


class ShowMusicTests(unittest.IsolatedAsyncioTestCase):
    async def test_show_music_starts_then_stops_on_cancel(self):
        scene_applied = asyncio.Event()

        async def apply(scene, group):
            scene_applied.set()
            return {"lamp": {"color": "accepted"}}

        music = {"player": "media_player.ma_room", "media_id": "library://playlist/42", "media_type": "playlist"}
        show = show_settings({"name": "Kerstshow", "group": "a" * 32, "music": music,
                              "steps": [{"scene": "b" * 32, "seconds": 20}]})
        lighting = SimpleNamespace(valid_show=lambda show: True, run_scene=apply)
        playback = Playback(lighting)
        calls = []
        supervisor = web.Application()

        async def respond(request):
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            calls.append((request.path, await request.json()))
            if request.path == "/template":
                return web.json_response([{"id": music["player"], "state": "idle"}])
            return web.json_response([])

        supervisor.router.add_post("/{path:.*}", respond)
        server = TestServer(supervisor)
        await server.start_server()
        self.addAsyncCleanup(server.close)
        with (patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test-token"}),
              patch("modules.lighting_projects.CORE_API", str(server.make_url("/")).rstrip("/"))):
            playback.start({**show, "id": "show"})
            task = playback.task
            await asyncio.wait_for(scene_applied.wait(), 2)
            playback.request_stop()
            await asyncio.wait_for(task, 2)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                await start_show_music({**music, "player": "media_player.regular_speaker"})
        self.assertIn("integration_entities('music_assistant')", calls[0][1]["template"])
        self.assertEqual(calls[1:3], [
            ("/services/music_assistant/play_media", {"entity_id": music["player"], "media_id": music["media_id"],
                                                     "enqueue": "play", "media_type": "playlist"}),
            ("/services/media_player/media_stop", {"entity_id": music["player"]}),
        ])
        self.assertEqual([path for path, _ in calls], [
            "/template", "/services/music_assistant/play_media", "/services/media_player/media_stop", "/template",
        ])
        self.assertEqual(playback.status["state"], "stopped")


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
            edit=asyncio.Lock(), music=set(), patterns={}, physical_tests={},
            ddp=SimpleNamespace(received=time.monotonic()),
            music_frame=lambda: bytes([255, 2, 1, 0, 0, 0]),
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
            "Govee.power": None,
        }.items():
            patcher = patch("modules.provider_routes." + name, new=AsyncMock(return_value=value))
            setattr(self, name.split(".")[-1], patcher.start())
            self.addCleanup(patcher.stop)
        app = web.Application()
        self.streamer = Mock(is_connected=True)
        entertainment = HueEntertainment(lambda: self.streamer)
        with patch("modules.provider_routes.HueEntertainment", return_value=entertainment):
            install(app, self.store, self.controller)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)

    def mock_entertainment(self, include_other=False):
        cfg = self.store.load()
        cfg["hue"]["bridge"]["client_key"] = "f" * 32
        self.store.save(cfg)
        members = [{"service": {"rid": "renderer", "rtype": "entertainment"}}]
        if include_other:
            members.append({"service": {"rid": "renderer-other", "rtype": "entertainment"}})
        self.profiles.return_value[0]["capabilities"]["rgb"] = True
        responses = {
            RESOURCE: [{"id": AREA, "metadata": {"name": "Living room"}, "status": "inactive",
                        "channels": [{"channel_id": 3, "members": members}]}],
            "light": [{"id": self.hue_id, "owner": {"rid": "lamp"}},
                      {"id": "another-light", "owner": {"rid": "other"}}],
            "entertainment": [{"id": "renderer", "owner": {"rid": "lamp"}},
                              {"id": "renderer-other", "owner": {"rid": "other"}}],
        }

        async def request(method, path, body=None):
            return responses[RESOURCE if path == RESOURCE + "/" + AREA else path] if method == "GET" else []

        patcher = patch("modules.provider_routes.Hue.request", new=AsyncMock(side_effect=request))
        self.addCleanup(patcher.stop)
        return patcher.start()

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

    async def test_hue_white_range_and_offline_lights_stay_on_home(self):
        profile = self.profiles.return_value[0]
        profile.update(status="online", temperature_mirek={"min": 153, "max": 500})
        profile["capabilities"]["temperature"] = True
        payload = {"id": self.hue, "action": "temperature", "value": 370}
        for value, outcome in ((370, "accepted"), (501, "skipped")):
            response = await self.client.post("/lighting/control", json={**payload, "value": value})
            self.assertEqual((await response.json())["results"], {self.hue: outcome})
        self.control.assert_awaited_once_with(self.hue_id, mirek=370)

        profile["status"] = "unavailable"
        response = await self.client.post("/lighting/control", json=payload)
        self.assertEqual((await response.json())["results"], {self.hue: "skipped"})
        self.profiles.side_effect = TimeoutError
        response = await self.client.get("/lighting")
        data = await response.json()
        self.assertEqual(data["connections"]["hue"][0]["status"], "unavailable")
        lights = {light["id"]: light for light in data["lights"]}
        self.assertEqual(lights[self.hue]["status"], "unavailable")
        self.control.assert_awaited_once()

    async def test_scene_applies_to_current_group_and_reports_each_command(self):
        group = "a" * 32
        self.store.save_groups({group: {"name": "Wall", "members": [self.twinkly]}})
        reply = await self.client.post("/lighting/scenes", json={
            "name": " Christmas Eve ", "group": group, "on": True,
            "brightness": 40, "color": [255, 10, 0],
        })
        self.assertEqual(reply.status, 200)
        scene = (await reply.json())["id"]
        self.assertEqual(ProviderStore(self.store.path.parent).load_scenes()[scene]["name"], "Christmas Eve")
        self.store.save_groups({group: {"name": "Wall", "members": [self.twinkly, self.hue, self.govee]}})
        reply = await self.client.post(f"/lighting/scenes/{scene}/apply")
        self.assertEqual(reply.status, 200)
        self.assertEqual((await reply.json())["results"], {
            self.twinkly: dict.fromkeys(("power", "color", "brightness"), "accepted"),
            self.hue: {"power": "accepted", "color": "skipped", "brightness": "skipped"},
            self.govee: {"power": "unconfirmed", "color": "unconfirmed", "brightness": "skipped"},
        })
        self.assertEqual([call.args[0]["action"] for call in self.controller.apply_control.await_args_list],
                         ["on", "color", "brightness"])

        self.store.save_groups({})
        reply = await self.client.post(f"/lighting/scenes/{scene}/apply")
        self.assertEqual(reply.status, 409)
        reply = await self.client.post("/lighting/scenes", json={"id": scene, "delete": True})
        self.assertEqual(reply.status, 200)
        self.assertEqual(self.store.load_scenes(), {})

    async def test_scene_rejects_invalid_input_and_off_only_sends_power(self):
        group = "a" * 32
        self.store.save_groups({group: {"name": "Wall", "members": [self.twinkly]}})
        payload = {"name": "Off", "group": group, "on": True}
        for change in ({"group": "missing"}, {"on": 1}, {"color": [0, 0, 0]}, {"brightness": 101}):
            response = await self.client.post("/lighting/scenes", json={**payload, **change})
            self.assertEqual(response.status, 400)
        reply = await self.client.post("/lighting/scenes", json={**payload, "on": False, "brightness": 20})
        self.assertEqual(reply.status, 200)
        scene = (await reply.json())["id"]
        reply = await self.client.post(f"/lighting/scenes/{scene}/apply")
        self.assertEqual((await reply.json())["results"], {self.twinkly: {"power": "accepted"}})
        self.controller.apply_control.assert_awaited_once_with({"id": "tree", "action": "off", "value": False})


    async def test_mixed_music_streams_hue_and_restores_govee_then_releases_twinkly(self):
        group = "a" * 32
        bridge = self.mock_entertainment()
        self.store.save_groups({group: {"name": "Wall", "members": [self.twinkly, self.hue, self.govee, self.silent]}})
        response = await self.client.post("/lighting/music", json={"group": group})
        self.assertEqual(response.status, 200, await response.text())
        info = await response.json()
        self.assertTrue(info["audio_received"])
        self.assertEqual(info["eligible"], [self.twinkly, self.hue, self.govee])
        self.assertEqual(info["skipped"], [self.silent])
        self.assertEqual(info["hue"], {"state": "streaming", "area": "Living room", "skipped": 0, "group": group})
        self.assertEqual(self.controller.music, {"tree"})
        async with asyncio.timeout(2):
            while not self.streamer.send_colors.called or not self.color.await_count:
                await asyncio.sleep(.01)
        self.color.assert_awaited_once_with([255, 0, 0])
        colors, = self.streamer.send_colors.call_args.args
        self.assertEqual((colors[0].channel_id, colors[0].red), (3, 65535))
        response = await self.client.get("/lighting")
        timings = (await response.json())["music"]["timings"]
        self.assertEqual(set(timings), {"govee"})
        self.assertEqual(timings["govee"]["failed"], 0)
        response = await self.client.post("/providers/hue/entertainment/control", json={"action": "stop"})
        self.assertEqual(response.status, 409)
        self.controller.music_frame = lambda: bytes([0, 0, 255])
        async with asyncio.timeout(2):
            while self.streamer.send_colors.call_args.args[0][0].blue != 65535:
                await asyncio.sleep(.01)
        response = await self.client.post("/lighting/music", json={"stop": True})
        self.assertEqual(await response.json(), {"group": None, "live": False, "restoration": {
            "twinkly_released": 1, "hue": "released", "color": {self.govee: "unconfirmed"},
        }})
        self.assertEqual(self.controller.music, set())
        self.control.assert_not_awaited()
        self.color.assert_awaited_with([255, 1, 2])
        bridge.assert_any_await("PUT", RESOURCE + "/" + AREA, {"action": "stop"})
        bridge.assert_awaited_with("GET", RESOURCE + "/" + AREA)
        self.streamer.disconnect.assert_called_once()

    async def test_music_stop_reports_unconfirmed_hue_release_and_failed_govee_restore(self):
        group = "a" * 32
        bridge = self.mock_entertainment()
        self.store.save_groups({group: {"name": "Wall", "members": [self.hue, self.govee]}})
        response = await self.client.post("/lighting/music", json={"group": group})
        self.assertEqual(response.status, 200)
        async with asyncio.timeout(2):
            while not self.color.await_count:
                await asyncio.sleep(.01)
        bridge.side_effect = OSError
        self.color.side_effect = OSError
        response = await self.client.post("/lighting/music", json={"stop": True})
        self.assertEqual(await response.json(), {"group": None, "live": False, "restoration": {
            "hue": "unconfirmed", "color": {self.govee: "failed"},
        }})

    async def test_music_skips_an_area_with_lights_outside_the_group(self):
        group = "a" * 32
        bridge = self.mock_entertainment(include_other=True)
        self.store.save_groups({group: {"name": "Wall", "members": [self.hue]}})
        response = await self.client.post("/lighting/music", json={"group": group})
        info = await response.json()
        self.assertIsNone(info["group"])
        self.assertEqual(info["hue"], {"state": "missing_area", "area": None, "skipped": 1, "group": group})
        self.assertEqual(info["skipped"], [self.hue])
        self.assertTrue(all(call.args[0] == "GET" for call in bridge.await_args_list))
        self.streamer.connect.assert_not_called()

    async def test_hue_test_center_starts_and_restores_a_single_lamp(self):
        light = {
            "id": self.hue_id, "on": {"on": False},
            "dimming": {"brightness": 43.25},
            "color": {"xy": {"x": .4, "y": .35}},
            "color_temperature": {"mirek": 300, "mirek_valid": True,
                                  "mirek_schema": {"mirek_minimum": 153, "mirek_maximum": 500}},
        }
        sent = asyncio.Event()
        reads = 0

        async def hue_request(method, path, body=None):
            self.assertEqual(path, "light/" + self.hue_id)
            nonlocal reads
            if method == "GET":
                reads += 1
                if reads == 2:
                    return [{**light, "on": {"on": True}}]
                return [light]
            sent.set()

        with patch("modules.provider_routes.Hue.request", new=AsyncMock(side_effect=hue_request)) as request:
            response = await self.client.post("/lighting/hue-test", json={"test": "rgb", "id": self.twinkly})
            self.assertEqual(response.status, 400)
            response = await self.client.post("/lighting/hue-test", json={"test": "rgb", "id": self.hue})
            self.assertEqual(response.status, 200, await response.text())
            self.assertEqual((await response.json())["result"], "running")
            await asyncio.wait_for(sent.wait(), 1)
            response = await self.client.post("/lighting/hue-test", json={"test": "stop"})
            self.assertEqual((await response.json())["result"], "restored")
            self.assertEqual(request.await_args_list[2].args[2], {
                "on": {"on": False}, "color_temperature": {"mirek": 300},
            })
            self.assertEqual(request.await_count, 5)
            light["effects"] = {"status": "candle"}
            response = await self.client.post("/lighting/hue-test", json={"test": "power", "id": self.hue})
            self.assertEqual(response.status, 409)


    async def test_hue_restore_is_unverified_when_bridge_keeps_reporting_test_state(self):
        from modules.hue_tests import confirm_restore

        read = AsyncMock(return_value={"on": {"on": True}})
        self.assertFalse(await confirm_restore(read, {"on": {"on": False}}))
        self.assertEqual(read.await_count, 3)


    async def test_govee_test_restores_power_and_requires_a_lan_status(self):
        sent = asyncio.Event()

        async def power(on):
            sent.set()

        with patch("modules.provider_routes.Govee.power", new=AsyncMock(side_effect=power)) as send:
            reply = await self.client.post("/lighting/govee-test", json={"test": "identify", "id": self.silent})
            self.assertEqual(reply.status, 409)
            reply = await self.client.post("/lighting/govee-test", json={"test": "identify", "id": self.govee})
            self.assertEqual(reply.status, 200, await reply.text())
            await asyncio.wait_for(sent.wait(), 1)
            reply = await self.client.post("/lighting/govee-test", json={"test": "stop"})
            self.assertEqual((await reply.json())["result"], "restored")
            self.assertEqual([call.args for call in send.await_args_list], [(False,), (True,)])

    async def test_govee_white_temperature_requires_reported_support(self):
        self.govee_statuses.return_value["192.168.1.3"]["colorTemInKelvin"] = 4200
        with patch("modules.govee.Govee.send", new=AsyncMock()) as send:
            response = await self.client.post("/lighting/control", json={
                "id": self.govee, "action": "temperature", "value": 3200,
            })
            self.assertEqual((await response.json())["results"], {self.govee: "unconfirmed"})
            send.assert_awaited_once_with(
                "colorwc", {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": 3200}
            )
            send.reset_mock()
            response = await self.client.post("/lighting/control", json={
                "id": self.silent, "action": "temperature", "value": 3200,
            })
            self.assertEqual((await response.json())["results"], {self.silent: "skipped"})
            send.assert_not_awaited()

    async def test_music_master_fader_scales_and_restores_the_group(self):
        group = "a" * 32
        self.store.save_groups({group: {"name": "Kerst", "members": [self.twinkly, self.hue, self.govee]}})
        self.profiles.return_value[0].update(
            capabilities={"brightness": True, "rgb": True},
            state={"on": True, "brightness": 80, "xy": {"x": .6, "y": .3}},
        )
        self.mock_entertainment()
        self.govee_statuses.return_value["192.168.1.3"]["brightness"] = 60
        with patch("modules.provider_routes.Govee.dim", new=AsyncMock()) as govee:
            response = await self.client.post("/lighting/music", json={"group": group})
            self.assertEqual(response.status, 200)
            response = await self.client.post("/lighting/music", json={"group": group, "level": 50})
            self.assertEqual((await response.json())["level"], 50)
            self.assertEqual(self.controller.mixed_music_levels, {"tree": 50})
            async with asyncio.timeout(2):
                while (not self.streamer.send_colors.called
                       or self.streamer.send_colors.call_args.args[0][0].red != 32768):
                    await asyncio.sleep(.01)
            govee.assert_awaited_once_with(30)
            response = await self.client.post("/lighting/music", json={"stop": True})
            self.assertEqual(response.status, 200)
            self.assertEqual(self.controller.mixed_music_levels, {})
            self.control.assert_not_awaited()
            govee.assert_awaited_with(60)

    async def test_home_room_assignment_and_filtered_scene_preserve_other_brands(self):
        response = await self.client.post("/lighting/groups", json={
            "kind": "room", "name": "Living room", "members": [self.twinkly],
        })
        self.assertEqual(response.status, 200)
        room = (await response.json())["id"]
        response = await self.client.post("/lighting/groups", json={"id": room, "member": self.hue})
        self.assertEqual(response.status, 200)
        self.assertEqual(self.store.load_groups()[room], {
            "kind": "room", "name": "Living room", "members": [self.twinkly, self.hue],
        })
        response = await self.client.post("/lighting/scenes", json={"name": "Evening", "group": room, "on": True})
        scene = (await response.json())["id"]
        response = await self.client.post(f"/lighting/scenes/{scene}/apply", json={"provider": "hue"})
        self.assertEqual((await response.json())["results"], {self.hue: {"power": "accepted"}})
        response = await self.client.post("/lighting/control", json={
            "group": room, "provider": "hue", "action": "power", "value": False,
        })
        self.assertEqual((await response.json())["results"], {self.hue: "accepted"})
        self.controller.apply_control.assert_not_awaited()

    async def test_home_commands_do_not_wait_for_a_new_provider_inventory(self):
        group = "b" * 32
        self.store.save_groups({group: {"name": "Living room", "kind": "room",
                                        "members": [self.twinkly, self.hue]}})
        response = await self.client.get("/lighting")
        self.assertEqual(response.status, 200)
        self.profiles.reset_mock()
        self.govee_statuses.reset_mock()
        response = await self.client.post("/lighting/control", json={
            "group": group, "action": "color", "value": [255, 0, 0],
        })
        self.assertEqual((await response.json())["results"], {self.twinkly: "accepted", self.hue: "skipped"})
        self.profiles.assert_not_awaited()
        self.govee_statuses.assert_not_awaited()
        self.controller.apply_control.assert_awaited_once_with(
            {"id": "tree", "action": "color", "value": "#ff0000"})

    async def test_uncached_hue_command_only_reads_hue(self):
        response = await self.client.post("/lighting/control", json={
            "id": self.hue, "action": "power", "value": True,
        })
        self.assertEqual((await response.json())["results"], {self.hue: "accepted"})
        self.profiles.assert_awaited_once()
        self.govee_statuses.assert_not_awaited()
