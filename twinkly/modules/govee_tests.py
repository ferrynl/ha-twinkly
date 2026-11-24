"""Build reversible Govee LAN test steps from the latest status report."""
from aiohttp import web

from .common import rgb
from .hue_tests import COLORS

TESTS = {"identify", "power", "brightness", *COLORS}


def test_state(report):
    power = report.get("onOff")
    state = {"on": {"on": bool(power) if type(power) is int and power in (0, 1) else None}}
    level = report.get("brightness")
    if type(level) is int and 1 <= level <= 100:
        state["dimming"] = {"brightness": level}
    color = report.get("color")
    if isinstance(color, dict) and not report.get("colorTemInKelvin"):
        try:
            state["rgb"] = rgb([color.get(channel) for channel in "rgb"])
        except ValueError:
            pass
    return state


def test_plan(state, test):
    power = state["on"]["on"]
    if power is None:
        raise web.HTTPConflict()
    restore = {"on": {"on": power}}
    if test == "identify":
        return [{"on": {"on": not power}}], restore
    if test == "power":
        return [{"on": {"on": value}} for value in (True, False)], restore
    if test == "brightness" and "dimming" in state:
        restore["dimming"] = state["dimming"]
        steps = [{"dimming": {"brightness": level}} for level in (20, 50, 80)]
    elif test in COLORS and "rgb" in state:
        restore["rgb"] = state["rgb"]
        steps = [{"rgb": list(color)} for color in COLORS[test]]
    else:
        raise web.HTTPConflict()
    steps[0]["on"] = {"on": True}
    return steps, restore
