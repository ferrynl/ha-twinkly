"""Conservative capability normalization for the shared lighting engine.

Unknown features remain disabled. Discovery does not authenticate devices.
"""
import math


def color_from_xy(xy):
    if not isinstance(xy, dict):
        return None
    x, y = xy.get("x"), xy.get("y")
    if not all(type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1 for v in (x, y)) or y < .001:
        return None
    X, Z = x / y, (1 - x - y) / y
    linear = (1.656492 * X - .354851 - .255038 * Z,
              -.707196 * X + 1.655397 + .036152 * Z,
              .051713 * X - .121364 + 1.011530 * Z)
    scale = max(1, *linear)
    channels = [max(0, value / scale) for value in linear]
    return [round(255 * (12.92 * c if c <= .0031308 else 1.055 * c ** (1 / 2.4) - .055))
            for c in channels]


def hue_profile(light, device=None):
    device=device or {}
    product=device.get("product_data") or {}
    metadata=light.get("metadata") or {}
    temperature=light.get("color_temperature")
    schema=(temperature.get("mirek_schema") or {}) if isinstance(temperature,dict) else {}
    if not isinstance(schema, dict):
        schema = {}
    low, high = schema.get("mirek_minimum"), schema.get("mirek_maximum")
    adjustable = type(low) is int and type(high) is int and 0 < low < high <= 1000
    mirek = temperature.get("mirek") if adjustable and temperature.get("mirek_valid") is True else None
    effect=light.get("effects")
    effects=effect.get("effect_values",[]) if isinstance(effect,dict) else []
    return {
        "provider":"hue","id":light["id"],"name":metadata.get("name") or light["id"],
        "model":product.get("model_id"),"product_name":product.get("product_name"),
        "archetype":(device.get("metadata") or {}).get("archetype") or metadata.get("archetype"),"firmware":product.get("software_version"),
        "capabilities":{"power":isinstance(light.get("on"),dict),
            "brightness":isinstance(light.get("dimming"),dict),
            "rgb":isinstance(light.get("color"),dict),
            "temperature":adjustable,
            "segments":False,"effects":sorted(set(x for x in effects if isinstance(x,str))) if isinstance(effects,list) else []},
        "temperature_mirek":{"min":low,"max":high} if adjustable else None,
        "state":{"on":(light.get("on") or {}).get("on"),"brightness":(light.get("dimming") or {}).get("brightness"),
                 "xy":(light.get("color") or {}).get("xy"),
                 "mirek":mirek if type(mirek) is int and low <= mirek <= high else None},
        "verified":True
    }

def hue_profiles(lights, devices, connectivity=()):
    devices_by_id = {row["id"]: row for row in devices
                     if isinstance(row, dict) and isinstance(row.get("id"), str)}
    links_by_owner = {(row.get("owner") or {}).get("rid"): row.get("status")
                      for row in connectivity if isinstance(row, dict)}
    status_by_link = {"connected": "online", "disconnected": "unavailable",
                      "connectivity_issue": "unavailable", "unidirectional_incoming": "unavailable"}
    profiles = []
    for light in lights:
        if not isinstance(light, dict) or not isinstance(light.get("id"), str):
            continue
        owner = (light.get("owner") or {}).get("rid")
        profile = hue_profile(light, devices_by_id.get(owner))
        profile["status"] = status_by_link.get(links_by_owner.get(owner), "unknown")
        profiles.append(profile)
    return profiles

def govee_profile(scan,status=None):
    # LAN scan advertises a model, not its supported commands.
    status=status or {}
    color=status.get("color")
    rgb=isinstance(color,dict) and all(type(color.get(c)) is int and 0<=color[c]<=255 for c in ("r","g","b"))
    level=status.get("brightness")
    temp=status.get("colorTemInKelvin")
    power=status.get("onOff")
    return {"provider":"govee","id":scan["device"],"name":scan["sku"] or scan["device"],"model":scan["sku"],
        "firmware":scan.get("wifiSoftVersion"),
        "capabilities":{"power":type(power) is int and power in (0,1),
            "brightness":type(level) is int and 0<=level<=100,"rgb":rgb,
            "temperature":type(temp) is int and 2000<=temp<=9000,"segments":False,"effects":[]},
        "state":{"on":bool(power) if type(power) is int and power in (0,1) else None,
            "brightness":level if type(level) is int and 0<=level<=100 else None,
            "color_temperature_kelvin":temp if type(temp) is int and temp > 0 else None,
                 "color":[color[c] for c in ("r","g","b")] if rgb else None},
        "verified":False}
