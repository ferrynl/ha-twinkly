"""Direct Govee LAN UDP control. No cloud or HA dependency."""
import asyncio
import json
import socket
from .common import lan_ip, rgb, brightness, RateGate

def packet(cmd, data):
    return json.dumps({"msg":{"cmd":cmd,"data":data}},separators=(",",":")).encode()

class Govee:
    def __init__(self,address):
        self.address = lan_ip(address)
        self.gate = RateGate(.2)

    async def send(self, cmd, data):
        async def dispatch():
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
                sock.setblocking(False)
                await asyncio.get_running_loop().sock_sendto(sock,packet(cmd,data),(self.address,4003))
        await self.gate.run(dispatch)

    async def power(self,on):
        if type(on) is not bool: raise ValueError("Invalid on state")
        await self.send("turn",{"value":int(on)})

    async def dim(self,level):
        await self.send("brightness",{"value":brightness(level)})

    async def color(self,value):
        r,g,b = rgb(value)
        await self.send("colorwc",{"color":{"r":r,"g":g,"b":b},"colorTemInKelvin":0})

    async def temperature(self, kelvin):
        if type(kelvin) is not int or not 2000 <= kelvin <= 9000:
            raise ValueError("Invalid color temperature")
        await self.send("colorwc", {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": kelvin})
