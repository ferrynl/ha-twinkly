"""Short, reversible Hue tests for the Test Center."""
import asyncio
import logging
import math

from aiohttp import ClientError, web

from .hue import xy_color


LOG = logging.getLogger(__name__)
ERRORS = (ClientError, OSError, RuntimeError, ValueError, TimeoutError)
COLORS = {
    "rgb": [(255, 0, 0), (0, 255, 0), (0, 0, 255)],
    "rainbow": [(255, 0, 0), (255, 128, 0), (255, 255, 0), (0, 255, 0),
                (0, 255, 255), (0, 0, 255), (255, 0, 255)],
}
TESTS = {"identify", "power", "brightness", "temperature", *COLORS}


def test_plan(light, test):
    power = (light.get("on") or {}).get("on")
    if type(power) is not bool:
        raise web.HTTPConflict()
    # A static command could replace a running effect or gradient.
    effect = (light.get("effects") or {}).get("status")
    effect_v2 = ((light.get("effects_v2") or {}).get("status") or {}).get("effect")
    if (effect not in (None, "no_effect") or effect_v2 not in (None, "no_effect")
            or (test in ({"temperature"} | COLORS.keys()) and (light.get("gradient") or {}).get("points"))):
        raise web.HTTPConflict()
    restore = {"on": {"on": power}}
    if test == "identify":
        return [{"on": {"on": not power}}], restore
    if test == "power":
        return [{"on": {"on": value}} for value in (True, False)], restore
    if test == "brightness":
        original = (light.get("dimming") or {}).get("brightness")
        if type(original) not in (int, float) or not 0 <= original <= 100:
            raise web.HTTPConflict()
        restore["dimming"] = {"brightness": original}
        return [{"on": {"on": True}, "dimming": {"brightness": value}} for value in (20, 50, 80)], restore

    temperature = light.get("color_temperature") or {}
    mirek = temperature.get("mirek")
    xy = (light.get("color") or {}).get("xy")
    if temperature.get("mirek_valid") and type(mirek) is int and 1 <= mirek <= 1000:
        restore["color_temperature"] = {"mirek": mirek}
    elif isinstance(xy, dict) and all(type(xy.get(axis)) in (float, int) and 0 <= xy[axis] <= 1 for axis in ("x", "y")):
        restore["color"] = {"xy": {"x": xy["x"], "y": xy["y"]}}
    else:
        raise web.HTTPConflict()
    if test in COLORS and xy is not None:
        changes = [{"color": {"xy": xy_color(color)}} for color in COLORS[test]]
    elif test == "temperature":
        schema = temperature.get("mirek_schema") or {}
        low, high = schema.get("mirek_minimum"), schema.get("mirek_maximum")
        if type(low) is not int or type(high) is not int or not 0 < low < high <= 1000:
            raise web.HTTPConflict()
        changes = [{"color_temperature": {"mirek": value}} for value in (high, low)]
    else:
        raise web.HTTPConflict()
    return [{"on": {"on": True}, **change} for change in changes], restore


def matches_snapshot(light, snapshot):
    if (light.get("on") or {}).get("on") is not snapshot["on"]["on"]:
        return False
    if "dimming" in snapshot:
        actual = (light.get("dimming") or {}).get("brightness")
        return type(actual) in (int, float) and math.isclose(
            actual, snapshot["dimming"]["brightness"], rel_tol=0, abs_tol=.5)
    if "color_temperature" in snapshot:
        temperature = light.get("color_temperature") or {}
        actual = temperature.get("mirek")
        return (temperature.get("mirek_valid") is True and type(actual) is int
                and abs(actual - snapshot["color_temperature"]["mirek"]) <= 1)
    if "rgb" in snapshot:
        return light.get("rgb") == snapshot["rgb"]
    if "color" in snapshot:
        if (light.get("color_temperature") or {}).get("mirek_valid") is True:
            return False
        actual = (light.get("color") or {}).get("xy") or {}
        expected = snapshot["color"]["xy"]
        return all(type(actual.get(axis)) in (int, float) and math.isclose(
            actual[axis], expected[axis], rel_tol=0, abs_tol=.005) for axis in ("x", "y"))
    return True


async def confirm_restore(read, snapshot):
    try:
        async with asyncio.timeout(3):
            for _ in range(3):
                await asyncio.sleep(.3)
                if matches_snapshot(await read(), snapshot):
                    return True
    except ERRORS:
        pass
    return False


class LampTest:
    def __init__(self):
        self.task = None
        self.wakeup = None
        self.target = None
        self.test = None
        self.result = None

    def status(self):
        return {"id": self.target, "test": self.test, "result": self.result}

    def start(self, target, test, send, read, changes, restore):
        self.target, self.test, self.result = target, test, "running"
        self.wakeup = asyncio.Event()
        self.task = asyncio.create_task(self.run(send, read, changes, restore))

    async def run(self, send, read, changes, restore):
        result = "restored"
        try:
            async with asyncio.timeout(15):
                for change in changes:
                    if self.wakeup.is_set():
                        break
                    await send(change)
                    try:
                        await asyncio.wait_for(self.wakeup.wait(), timeout=1.5)
                    except TimeoutError:
                        continue
                    break
        except ERRORS:
            result = "failed"
        finally:
            try:
                await send(restore)
            except ERRORS:
                LOG.warning("Failed to restore light after test", exc_info=True)
                result = "restore_failed"
            else:
                if not await confirm_restore(read, restore):
                    LOG.warning("Provider did not confirm the restored state for %s", self.target)
                    result = "restore_unverified"
            self.result = result

    async def stop(self):
        if self.task is not None and not self.task.done():
            self.wakeup.set()
            await self.task
