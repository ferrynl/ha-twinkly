"""Direct Hue CLIP v2 transport with caller-supplied verified TLS context."""
import re
import ssl
from aiohttp import ClientSession, ClientTimeout, Fingerprint
from .common import lan_ip, rgb, brightness, RateGate

def xy_color(value):
    r,g,b = [v/255 for v in rgb(value)]
    r,g,b = [((v+.055)/1.055)**2.4 if v>.04045 else v/12.92 for v in (r,g,b)]
    x = .664511*r+.154324*g+.162028*b
    y = .283881*r+.668433*g+.047685*b
    z = .000088*r+.072310*g+.986039*b
    total = x+y+z
    if not total:
        raise ValueError("Use off for black")
    return {"x":x/total,"y":y/total}

class Hue:
    def __init__(self, address, application_key, tls):
        if not isinstance(tls, Fingerprint) and (not isinstance(tls, ssl.SSLContext) or tls.verify_mode != ssl.CERT_REQUIRED or not tls.check_hostname):
            raise ValueError("Verified TLS context required")
        self.address = lan_ip(address)
        self.key = application_key
        self.tls = tls
        self.gate = RateGate(.15)

    async def request(self, method, path, body=None):
        async def send():
            async with ClientSession(timeout=ClientTimeout(total=5)) as session:
                async with session.request(method, f"https://{self.address}/clip/v2/resource/{path}",
                    headers={"hue-application-key":self.key}, json=body, ssl=self.tls,
                    allow_redirects=False) as response:
                    response.raise_for_status()
                    data = await response.json()
                    if data.get("errors"):
                        raise RuntimeError("Hue rejected request")
                    return data.get("data", [])
        return await self.gate.run(send)

    async def lights(self):
        return await self.request("GET","light")

    async def profiles(self):
        from .profiles import hue_profiles
        return hue_profiles(await self.lights(), await self.request("GET","device"))

    async def control(self, light_id, *, on=None, level=None, color=None):
        if not re.fullmatch(r"[0-9a-fA-F-]{36}",light_id):
            raise ValueError("Invalid resource ID")
        body = {}
        if on is not None:
            if type(on) is not bool: raise ValueError("Invalid on state")
            body["on"] = {"on":on}
        if level is not None: body["dimming"] = {"brightness":brightness(level)}
        if color is not None: body["color"] = {"xy":xy_color(color)}
        if not body: raise ValueError("Empty command")
        return await self.request("PUT","light/"+light_id,body)
