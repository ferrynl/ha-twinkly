"""Conservative capability normalization for the shared lighting engine.

Unknown features remain disabled. Discovery does not authenticate devices.
"""
def hue_profile(light, device=None):
    device=device or {}
    product=device.get("product_data") or {}
    metadata=light.get("metadata") or {}
    temperature=light.get("color_temperature")
    schema=temperature.get("mirek_schema",{}) if isinstance(temperature,dict) else {}
    effect=light.get("effects")
    effects=effect.get("effect_values",[]) if isinstance(effect,dict) else []
    return {
        "provider":"hue","id":light["id"],"name":metadata.get("name") or light["id"],
        "model":product.get("model_id"),"firmware":product.get("software_version"),
        "capabilities":{"power":isinstance(light.get("on"),dict),
            "brightness":isinstance(light.get("dimming"),dict),
            "rgb":isinstance(light.get("color"),dict),
            "temperature":isinstance(temperature,dict),
            "segments":False,"effects":sorted(set(x for x in effects if isinstance(x,str))) if isinstance(effects,list) else []},
        "temperature_mirek":{"min":schema.get("mirek_minimum"),"max":schema.get("mirek_maximum")} if isinstance(temperature,dict) else None,
        "state":{"on":(light.get("on") or {}).get("on"),"brightness":(light.get("dimming") or {}).get("brightness"),
                 "xy":(light.get("color") or {}).get("xy")},
        "verified":True
    }

def hue_profiles(lights,devices):
    lookup={d["id"]:d for d in devices if isinstance(d,dict) and isinstance(d.get("id"),str)}
    return [hue_profile(l,lookup.get((l.get("owner") or {}).get("rid"))) for l in lights if isinstance(l,dict) and isinstance(l.get("id"),str)]

def govee_profile(scan,status=None):
    # LAN scan advertises a model, not its supported commands.
    status=status or {}
    color=status.get("color")
    rgb=isinstance(color,dict) and all(type(color.get(c)) is int and 0<=color[c]<=255 for c in ("r","g","b"))
    level=status.get("brightness")
    temp=status.get("colorTemInKelvin")
    power=status.get("onOff")
    return {"provider":"govee","id":scan["device"],"name":scan["sku"],"model":scan["sku"],
        "firmware":scan.get("wifiSoftVersion"),
        "capabilities":{"power":type(power) is int and power in (0,1),
            "brightness":type(level) is int and 0<=level<=100,"rgb":rgb,
            "temperature":type(temp) is int and 2000<=temp<=9000,"segments":False,"effects":[]},
        "state":{"on":bool(power) if type(power) is int and power in (0,1) else None,
            "brightness":level if type(level) is int and 0<=level<=100 else None,
                 "color":[color[c] for c in ("r","g","b")] if rgb else None},
        "verified":False}
