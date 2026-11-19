import asyncio
import ipaddress

def lan_ip(value):
    address = ipaddress.IPv4Address(value)
    if not any(address in ipaddress.IPv4Network(n) for n in ("10.0.0.0/8","172.16.0.0/12","192.168.0.0/16")):
        raise ValueError("Expected private LAN IPv4 address")
    return str(address)

def rgb(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3 or any(type(x) is not int or not 0 <= x <= 255 for x in value):
        raise ValueError("Invalid RGB")
    return list(value)

def brightness(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("Invalid brightness")
    return value

class RateGate:
    def __init__(self, interval):
        self.interval = interval
        self.lock = asyncio.Lock()
        self.next = 0

    async def run(self, send):
        async with self.lock:
            loop = asyncio.get_running_loop()
            await asyncio.sleep(max(0, self.next-loop.time()))
            try:
                return await send()
            finally:
                self.next = loop.time()+self.interval
