"""Local Govee multicast discovery; only trust validated LAN packet sources."""
import asyncio
import json
import socket
from .common import lan_ip
from .govee import packet

def parse_scan(data, source):
    try:
        ip = lan_ip(source[0])
        msg = json.loads(data)["msg"]
        if msg["cmd"] != "scan":
            return None
        d = msg["data"]
        device, sku = d["device"], d["sku"]
        if not isinstance(device,str) or not isinstance(sku,str) or not device or not sku or len(device)>128 or len(sku)>64:
            return None
        if d.get("ip") != ip:
            return None
        return {"ip":ip,"device":device,"sku":sku}
    except (ValueError, TypeError, KeyError, IndexError, UnicodeError):
        return None

async def discover(timeout=3):
    if not 0 < timeout <= 10:
        raise ValueError("Invalid scan timeout")
    loop = asyncio.get_running_loop()
    found = {}
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(("0.0.0.0",4002))
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,1)
        await loop.sock_sendto(sock,packet("scan",{"account_topic":"reserve"}),("239.255.255.250",4001))
        end=loop.time()+timeout
        while loop.time()<end:
            try:
                data,source=await asyncio.wait_for(loop.sock_recvfrom(sock,8192),max(0,end-loop.time()))
            except asyncio.TimeoutError:
                break
            item=parse_scan(data,source)
            if item:
                found[item["device"]]=item
    return sorted(found.values(),key=lambda item:item["device"])
