import asyncio
import base64
from io import BytesIO
import stat
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiohttp import ClientSession, WSMsgType, web
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image

from modules.lighting_projects import install, spatial_steps
from modules.provider_store import ProviderStore

GROUP = "1" * 32
FIRST = "2" * 32
SECOND = "3" * 32
POINT = ['["hue","bridge","lamp"]', [50, 75]]
SHOW = {"name": "Kerst", "group": GROUP, "steps": [{"scene": FIRST, "seconds": 20},
                                                   {"scene": SECOND, "seconds": 1}]}


class LightingProjectsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = ProviderStore(directory.name)
        self.lighting = SimpleNamespace(store=self.store, valid_show=lambda show: show["group"] == GROUP,
                                        run_scene=AsyncMock(return_value={"light": {"power": "accepted"}}))
        self.client = await self.connect()

    async def connect(self):
        app = web.Application(client_max_size=720_000)
        install(app, self.lighting)
        client = TestClient(TestServer(app))
        await client.start_server()
        self.addAsyncCleanup(client.close)
        return client

    async def test_home_assistant_demo_event_only_controls_the_selected_room(self):
        member = POINT[0]
        self.store.save_groups({GROUP: {"name": "Woonkamer", "kind": "room", "members": [member]}})
        light = {"status": "online", "capabilities": {"rgb": True, "power": True}}
        self.lighting.command_lights = AsyncMock(return_value={member: light})
        self.lighting.spatial_groups = lambda groups: {}
        self.lighting.control_lock = asyncio.Lock()
        self.lighting.music = SimpleNamespace(members=set())
        self.lighting.lamp_test = None
        self.lighting.send = AsyncMock(return_value="accepted")
        queued = asyncio.Event()

        async def events():
            yield SimpleNamespace(type=WSMsgType.TEXT, json=lambda: {
                "type": "event", "event": {"data": {"room": "Woonkamer"}}
            })
            await queued.wait()

        socket = AsyncMock()
        socket.receive_json.side_effect = [{"type": "auth_required"}, {"type": "auth_ok"}, {"success": True}]
        socket.__aiter__.side_effect = events
        session = AsyncMock()
        session.ws_connect = lambda *args, **kwargs: socket
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test-token"}), \
                patch("modules.lighting_projects.ClientSession", return_value=session):
            session.__aenter__.return_value = session
            socket.__aenter__.return_value = socket
            client = await self.connect()
            for _ in range(100):
                if self.lighting.send.await_count >= 3:
                    break
                await asyncio.sleep(.02)
            self.assertEqual([call.args for call in self.lighting.send.await_args_list[:3]], [
                (member, light, "power", False),
                (member, light, "color", [225, 38, 69]),
                (member, light, "power", True),
            ])
            self.assertEqual(socket.send_json.await_args_list[1].args[0]["event_type"],
                             "christmas_control_center_demo")
            await client.close()

    async def test_home_assistant_event_plays_the_saved_show(self):
        saved = await (await self.change("save", **SHOW)).json()
        show_id = saved["shows"][0]["id"]
        queued = asyncio.Event()

        async def events():
            yield SimpleNamespace(type=WSMsgType.TEXT, json=lambda: {
                "type": "event", "event": {"data": {"show_id": show_id}}
            })
            await queued.wait()

        socket = AsyncMock()
        socket.receive_json.side_effect = [{"type": "auth_required"}, {"type": "auth_ok"}, {"success": True}]
        socket.__aiter__.side_effect = events
        session = AsyncMock()
        session.ws_connect = lambda *args, **kwargs: socket
        with patch.dict("os.environ", {"SUPERVISOR_TOKEN": "test-token"}), \
                patch("modules.lighting_projects.ClientSession", return_value=session):
            session.__aenter__.return_value = session
            socket.__aenter__.return_value = socket
            client = await self.connect()
            for _ in range(100):
                if self.lighting.run_scene.await_count:
                    break
                await asyncio.sleep(.02)
            self.lighting.run_scene.assert_any_await(FIRST, GROUP)
            self.assertEqual(socket.send_json.await_args_list[1].args[0]["event_type"],
                             "christmas_control_center_demo")
            await client.close()

    async def change(self, action, **body):
        return await self.client.post("/lighting/projects", json={"action": action, **body})

    @staticmethod
    def image(color="red"):
        out = BytesIO()
        exif = Image.Exif()
        exif[270] = "Private photo metadata"
        Image.new("RGB", (20, 10), color).save(out, "JPEG", exif=exif)
        return base64.b64encode(out.getvalue()).decode("ascii")

    async def test_photo_and_shows_persist_with_private_permissions(self):
        saved = await self.change("save", **SHOW)
        self.assertEqual(saved.status, 200)
        self.assertEqual((await saved.json())["shows"][0]["steps"], SHOW["steps"])
        uploaded = await self.change("layout", revision=None, photo=self.image(), points=[POINT])
        self.assertEqual(uploaded.status, 200)
        layout = (await uploaded.json())["layout"]
        self.assertNotIn("photo", layout)
        self.assertTrue(layout["photo_version"])
        path = self.store.path.parent / "lighting-projects.json"
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

        restarted = await self.connect()
        status = await restarted.get("/lighting/projects")
        self.assertIn("no-store", status.headers["Cache-Control"])
        data = await status.json()
        self.assertEqual(data["layout"]["points"], [POINT])
        self.assertEqual(data["shows"][0]["name"], "Kerst")
        photo = await restarted.get("/lighting/projects/photo")
        self.assertEqual(photo.content_type, "image/jpeg")
        self.assertIn("no-store", photo.headers["Cache-Control"])
        with Image.open(BytesIO(await photo.read())) as image:
            self.assertEqual(image.size, (20, 10))
            self.assertNotIn(270, image.getexif())

    async def test_rejected_photo_and_stale_revisions_leave_data_unchanged(self):
        invalid = await self.change("layout", revision=None, photo="abc", points=[])
        self.assertEqual(invalid.status, 400)
        self.assertEqual((await self.client.get("/lighting/projects/photo")).status, 404)
        uploaded = await self.change("layout", revision=None, photo=self.image(), points=[POINT])
        previous = (await uploaded.json())["layout"]
        stale = await self.change("layout", revision=None, points=[])
        self.assertEqual(stale.status, 409)
        moved = await self.change("layout", revision=previous["revision"], points=[])
        self.assertEqual((await moved.json())["layout"]["photo_version"], previous["photo_version"])
        saved = await self.change("save", **SHOW)
        show = (await saved.json())["shows"][0]
        changed = await self.change("save", **{**show, "name": "Updated"})
        self.assertEqual(changed.status, 200)
        stale = await self.change("delete", id=show["id"], revision=show["revision"])
        self.assertEqual(stale.status, 409)

    async def test_measured_wall_without_photo_persists_and_keeps_its_lamps_on_upload(self):
        rejected = await self.change("layout", revision=None, points=[POINT])
        self.assertEqual(rejected.status, 400)
        for width in (True, None, "3.25", 0, 21):
            invalid = await self.change("wall_dimensions", revision=None, width_m=width, height_m=2.6)
            self.assertEqual(invalid.status, 400)
        saved = await self.change("wall_dimensions", revision=None, width_m=3.25, height_m=2.6)
        self.assertEqual(saved.status, 200)
        layout = (await saved.json())["layout"]
        dimensions = {"width_m": 3.25, "height_m": 2.6}
        self.assertEqual(layout["dimensions"], dimensions)
        stale = await self.change("wall_dimensions", revision=None, width_m=4, height_m=2.6)
        self.assertEqual(stale.status, 409)
        placed = await self.change("layout", revision=layout["revision"], points=[POINT])
        self.assertEqual(placed.status, 200)
        before = (await placed.json())["layout"]
        restarted = await self.connect()
        plan = await (await restarted.get("/lighting/projects/overview")).json()
        self.assertEqual(plan["walls"][0]["dimensions"], dimensions)
        self.assertEqual(plan["walls"][0]["points"], [POINT])
        self.assertIsNone(plan["walls"][0]["photo_version"])
        photo = await restarted.post("/lighting/projects", json={
            "action": "layout", "revision": before["revision"], "points": before["points"], "photo": self.image(),
        })
        self.assertEqual(photo.status, 200)
        self.assertEqual((await photo.json())["layout"]["dimensions"], dimensions)

    async def test_lamp_scale_is_validated_and_preserved_with_legacy_points(self):
        other = ['["twinkly","strings"]', [12, 55, 24, 75, -35]]
        layout = await self.change("layout", revision=None, photo=self.image(), points=[POINT, other])
        self.assertEqual(layout.status, 200)
        before = (await layout.json())["layout"]
        self.assertEqual(before["points"], [POINT, other])
        invalid = await self.change("layout", revision=before["revision"], points=[[other[0], [12, 55, 41]]])
        self.assertEqual(invalid.status, 400)
        invalid = await self.change("layout", revision=before["revision"], points=[[other[0], [12, 55, 24, 75, 181]]])
        self.assertEqual(invalid.status, 400)
        status = await self.client.get("/lighting/projects")
        self.assertEqual((await status.json())["layout"], before)

    async def test_import_deduplicates_shows_and_preserves_existing_photo(self):
        data = {"shows": [SHOW], "photo": self.image(), "points": [POINT]}
        first = await self.change("import", **data)
        first_data = await first.json()
        self.assertTrue(first_data["imported_photo"])
        again = await self.change("import", **{**data, "points": []})
        again_data = await again.json()
        self.assertFalse(again_data["imported_photo"])
        self.assertEqual(again_data["shows"], first_data["shows"])
        self.assertEqual(again_data["layout"], first_data["layout"])

    async def test_playback_survives_client_disconnect_and_stops_between_steps(self):
        started = asyncio.Event()

        async def apply(scene, group):
            started.set()
            return {"light": {"power": "unconfirmed"}}

        self.lighting.run_scene.side_effect = apply
        result = await self.change("save", **SHOW)
        identifier = (await result.json())["shows"][0]["id"]
        async with ClientSession() as starter:
            async with starter.post(self.client.make_url("/lighting/projects"),
                                    json={"action": "play", "id": identifier}) as response:
                self.assertEqual(response.status, 200)
        await asyncio.wait_for(started.wait(), 2)
        status = await self.client.get("/lighting/projects")
        self.assertEqual((await status.json())["playback"]["state"], "playing")
        self.assertEqual((await self.change("play", id=identifier)).status, 409)
        await self.change("stop")
        for _ in range(30):
            status = await self.client.get("/lighting/projects")
            if (await status.json())["playback"]["state"] == "stopped":
                break
            await asyncio.sleep(0.01)
        else:
            self.fail("Show did not stop")
        self.lighting.run_scene.assert_awaited_once_with(FIRST, GROUP)

    async def test_spatial_effect_follows_photo_coordinates_and_skips_off_lights(self):
        left = '["twinkly","tree"]'
        right = '["hue","bridge","right"]'
        off = '["govee","off","off"]'
        lights = {
            key: {"status": "online", "capabilities": {"rgb": True}, "state": {"on": key != off}}
            for key in (left, right, off)
        }
        self.lighting.lights = AsyncMock(return_value=(lights, {}))
        self.lighting.send_spatial_color = AsyncMock(side_effect=["unconfirmed", "accepted"])
        response = await self.change("layout", revision=None, photo=self.image(),
                                     points=[[left, [14, 50]], [off, [40, 50]], [right, [88, 60]]])
        revision = (await response.json())["layout"]["revision"]
        args = {"revision": revision, "direction": "left", "color": [255, 10, 20], "delay": 250}
        self.assertEqual((await self.change("spatial", **{**args, "revision": None})).status, 409)
        response = await self.change("spatial", **args)
        self.assertEqual(response.status, 200)
        for _ in range(150):
            state = (await (await self.client.get("/lighting/projects")).json())["playback"]
            if state["state"] != "playing":
                break
            await asyncio.sleep(.01)
        self.assertEqual(state["state"], "complete")
        self.assertEqual(state["kind"], "spatial")
        self.assertTrue(state["uncertain"])
        self.assertEqual(state["last"]["results"], {left: {"color": "accepted"}})
        self.assertGreaterEqual(state["last"]["milliseconds"], 0)
        self.assertEqual([row["lamp"] for row in state["timing"]][-1], left)
        self.assertEqual(len(state["timing"]), state["total"])
        for row in state["timing"]:
            self.assertGreaterEqual(row["planned_ms"], 0)
            self.assertGreaterEqual(row["sent_ms"], 0)
            self.assertGreaterEqual(row["command_ms"], 0)
        self.assertEqual([call.args[0] for call in self.lighting.send_spatial_color.await_args_list], [right, left])

    async def test_timing_offset_is_persisted_and_bounded(self):
        key = '["twinkly","tree"]'
        point = [42, 51, 12, 650]
        saved = await self.change("layout", revision=None, photo=self.image(), points=[[key, point]])
        self.assertEqual(saved.status, 200)
        layout = (await saved.json())["layout"]
        self.assertEqual(layout["points"], [[key, point]])
        invalid = await self.change("layout", revision=layout["revision"], points=[[key, [42, 51, 12, 1001]]])
        self.assertEqual(invalid.status, 400)
        restarted = await self.connect()
        self.assertEqual((await (await restarted.get("/lighting/projects")).json())["layout"]["points"], [[key, point]])

    def test_gradient_colors_and_correction_use_geometry_and_planned_dispatch(self):
        points = [("left", [10, 0]), ("middle", [30, 0, 12, 50]), ("right", [90, 0, 12, 500, -35])]
        lights = {key: {} for key, _ in points}
        steps = spatial_steps(points, lights, 0, 1, [255, 0, 0], 250, [0, 0, 255])
        self.assertEqual([step["lamp"] for step in steps], ["right", "middle", "left"])
        self.assertEqual([step["color"] for step in steps], [[0, 0, 255], [191, 0, 64], [255, 0, 0]])
        self.assertEqual([step["due"] for step in steps], [0, 0.45, 0.5])
        sweep = spatial_steps(points, lights, 0, 1, [255, 0, 0], 250, None)
        self.assertEqual([step["lamp"] for step in sweep], ["left", "right", "middle"])
        self.assertEqual([step["due"] for step in sweep], [0, 0, 0.2])

    async def test_saved_walls_keep_independent_photos_and_positions(self):
        self.store.write(self.store.path.parent / "lighting-projects.json", {
            "shows": {}, "layout": {"revision": "legacy", "photo_version": "legacy",
                                    "photo": self.image(), "points": [POINT]}
        })
        added = await self.change("add_wall", name="Woonkamer")
        self.assertEqual(added.status, 200)
        selected = await added.json()
        wall = selected["wall_id"]
        second_point = [POINT[0], [20, 35, 12, 120]]
        latest = await self.client.post("/lighting/projects", params={"wall": wall}, json={
            "action": "layout", "revision": selected["layout"]["revision"],
            "photo": self.image("blue"), "points": [second_point]
        })
        self.assertEqual(latest.status, 200)
        revision = (await latest.json())["layout"]["revision"]
        stale = await self.client.post("/lighting/projects", params={"wall": wall}, json={
            "action": "layout", "revision": "legacy", "points": []
        })
        self.assertEqual(stale.status, 409)

        restarted = await self.connect()
        primary = await (await restarted.get("/lighting/projects")).json()
        self.assertEqual(primary["layout"]["points"], [POINT])
        other = await (await restarted.get("/lighting/projects", params={"wall": wall})).json()
        self.assertEqual(other["walls"][1]["name"], "Woonkamer")
        self.assertEqual(other["layout"]["points"], [second_point])
        first_photo = await (await restarted.get("/lighting/projects/photo")).read()
        second_photo = await (await restarted.get("/lighting/projects/photo", params={"wall": wall})).read()
        self.assertNotEqual(first_photo, second_photo)
        removed = await restarted.post("/lighting/projects", params={"wall": wall}, json={
            "action": "delete_wall", "revision": revision
        })
        self.assertEqual((await removed.json())["layout"]["points"], [POINT])
        self.assertEqual((await restarted.get("/lighting/projects/photo", params={"wall": wall})).status, 404)

    async def test_radial_effects_dispatch_from_centre_and_edges(self):
        points = [
            ['["hue","bridge","near"]', [52, 50]],
            ['["hue","bridge","far"]', [15, 15]],
            ['["hue","bridge","middle"]', [52, 25, 10, 0]],
        ]
        self.lighting.lights = AsyncMock(return_value=({
            key: {"status": "online", "state": {"on": True}, "capabilities": {"rgb": True}}
            for key, _ in points
        }, {}))
        dispatch = asyncio.Queue()

        async def color(key, light, value, stop):
            dispatch.put_nowait(key)
            return "accepted"

        self.lighting.send_spatial_color = color
        result = await self.change("layout", revision=None, photo=self.image(), points=points)
        revision = (await result.json())["layout"]["revision"]
        for effect, order in (("outward", [0, 2, 1]), ("inward", [1, 2, 0])):
            with self.subTest(effect=effect):
                result = await self.change("spatial", revision=revision, effect=effect, color=[255, 20, 1], delay=250)
                self.assertEqual(result.status, 200)
                self.assertEqual((await result.json())["playback"]["effect"], effect)
                self.assertEqual([await asyncio.wait_for(dispatch.get(), 2) for _ in order],
                                 [points[i][0] for i in order])
                stopped = await self.change("stop")
                self.assertEqual(stopped.status, 200)
                for _ in range(20):
                    state = await (await self.client.get("/lighting/projects")).json()
                    if state["playback"]["state"] in ("complete", "stopped"):
                        break
                    await asyncio.sleep(.01)
                self.assertIn(state["playback"]["state"], ("complete", "stopped"))

    async def test_plan_slots_swap_persist_and_reject_a_stale_edit(self):
        first = await self.change("layout", revision=None, photo=self.image(), points=[POINT])
        self.assertEqual(first.status, 200)
        added = await self.change("add_wall", name="Zijwand")
        wall = (await added.json())["wall_id"]
        url = "/lighting/projects/overview"
        initial = await (await self.client.get(url)).json()
        self.assertEqual([(row["id"], row["slot"]) for row in initial["walls"]],
                         [("default", 0), (wall, 1)])

        moved = await self.client.post(url, json={"wall": "default", "slot": 1,
                                                   "revision": initial["revision"]})
        self.assertEqual(moved.status, 200)
        changed = await moved.json()
        self.assertEqual([(row["id"], row["slot"]) for row in changed["walls"]],
                         [(wall, 0), ("default", 1)])
        self.assertEqual(changed["walls"][1]["points"], [POINT])
        stale = await self.client.post(url, json={"wall": wall, "slot": 5,
                                                   "revision": initial["revision"]})
        self.assertEqual(stale.status, 409)
        invalid = await self.client.post(url, json={"wall": wall, "slot": True,
                                                     "revision": changed["revision"]})
        self.assertEqual(invalid.status, 400)

        restarted = await self.connect()
        self.assertEqual(await (await restarted.get(url)).json(), changed)
        wall_data = await (await restarted.get("/lighting/projects", params={"wall": wall})).json()
        response = await restarted.post("/lighting/projects", params={"wall": wall}, json={
            "action": "delete_wall", "revision": wall_data["layout"]["revision"]
        })
        self.assertEqual(response.status, 200)
        remaining = await (await restarted.get(url)).json()
        self.assertEqual(remaining["walls"], [changed["walls"][1]])

    async def test_plan_coordinates_and_room_names_persist_and_can_be_reset(self):
        url = "/lighting/projects/overview"
        initial = await (await self.client.get(url)).json()
        body = {"wall": "default", "slot": 0, "revision": initial["revision"],
                "placement": {"x_m": 1.257, "z_m": -2, "angle": 35}, "room_name": " Woonkamer "}
        invalid = await self.client.post(url, json={**body, "placement": {**body["placement"], "x_m": True}})
        self.assertEqual(invalid.status, 400)
        saved = await self.client.post(url, json=body)
        self.assertEqual(saved.status, 200)
        changed = await saved.json()
        self.assertEqual(changed["walls"][0]["placement"], {"x_m": 1.26, "z_m": -2, "angle": 35})
        self.assertEqual(changed["room_names"], {"0": "Woonkamer"})
        stale = await self.client.post(url, json={**body, "placement": None})
        self.assertEqual(stale.status, 409)
        restarted = await self.connect()
        self.assertEqual(await (await restarted.get(url)).json(), changed)
        reset = await restarted.post(url, json={**body, "revision": changed["revision"],
                                                "placement": None, "room_name": ""})
        self.assertEqual(await reset.json(), initial)
        moved = await restarted.post(url, json={**body, "slot": 31})
        last_room = await moved.json()
        self.assertEqual(last_room["walls"][0]["slot"], 31)
        self.assertEqual(last_room["room_names"], {"7": "Woonkamer"})
        invalid = await restarted.post(url, json={**body, "slot": 32, "revision": last_room["revision"]})
        self.assertEqual(invalid.status, 400)

    async def test_floor_plan_tree_validates_persists_and_can_be_removed(self):
        url = "/lighting/projects/overview"
        before = await (await self.client.get(url)).json()
        tree = {"x_m": 0.75, "z_m": -1.5, "height_m": 2.4, "angle": -30}
        body = {"room": 0, "tree": tree, "revision": before["revision"]}
        invalid = await self.client.post(url + "/tree", json={**body, "tree": {**tree, "height_m": True}})
        self.assertEqual(invalid.status, 400)
        other_room = await self.client.post(url + "/tree", json={**body, "room": 7})
        self.assertEqual(other_room.status, 409)

        placed = await self.client.post(url + "/tree", json=body)
        self.assertEqual(placed.status, 200)
        changed = await placed.json()
        self.assertEqual(changed["trees"], {"0": tree})
        stale = await self.client.post(url + "/tree", json={**body, "tree": None})
        self.assertEqual(stale.status, 409)
        wall_edit = await self.client.post(url, json={"wall": "default", "slot": 1, "revision": before["revision"]})
        self.assertEqual(wall_edit.status, 409)

        restarted = await self.connect()
        self.assertEqual(await (await restarted.get(url)).json(), changed)
        removed = await restarted.post(url + "/tree", json={**body, "tree": None, "revision": changed["revision"]})
        self.assertEqual(removed.status, 200)
        self.assertEqual(await removed.json(), before)

    async def test_spatial_groups_play_once_with_individual_results_inside_the_group(self):
        group = '["group","twinkly:native:wall"]'
        members = ['["twinkly","a"]', '["twinkly","b"]']
        self.lighting.spatial_groups = lambda: {group: {"name": "Wall", "members": members}}
        lights = {key: {"status": "online", "capabilities": {"rgb": True}, "state": {"on": True}}
                  for key in members}
        self.lighting.lights = AsyncMock(return_value=(lights, {}))
        self.lighting.send_spatial_group_color = AsyncMock(return_value={key: "accepted" for key in members})
        initial = await self.change("layout", revision=None, photo=self.image(),
                                    points=[[members[0], [20, 20]], [members[1], [30, 30]], [group, [40, 40]]])
        self.assertEqual(initial.status, 200)
        revision = (await initial.json())["layout"]["revision"]
        await self.change("spatial", revision=revision, direction="right", color=[255, 0, 0], delay=250)
        for _ in range(50):
            status = (await (await self.client.get("/lighting/projects")).json())["playback"]
            if status["state"] == "complete":
                break
            await asyncio.sleep(0.01)
        self.assertEqual(status["state"], "complete")
        self.assertEqual(status["total"], 1)
        self.assertEqual(status["last"]["results"], {group: {key: "accepted" for key in members}})
        self.lighting.send_spatial_group_color.assert_awaited_once()
        self.assertEqual(self.lighting.send_spatial_group_color.await_args.args[0], lights)
