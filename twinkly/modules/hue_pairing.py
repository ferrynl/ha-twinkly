"""Hue local pairing using an explicitly trusted bridge certificate fingerprint."""
import re
from aiohttp import ClientSession, ClientTimeout, Fingerprint
from .common import lan_ip

def fingerprint(value):
    if not isinstance(value,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",value):
        raise ValueError("Expected SHA256 certificate fingerprint")
    return Fingerprint(bytes.fromhex(value))

def pairing_result(payload):
    if not isinstance(payload,list) or len(payload)!=1 or not isinstance(payload[0],dict):
        raise ValueError("Invalid Hue pairing response")
    item=payload[0]
    if "error" in item:
        error=item["error"]
        if isinstance(error,dict) and error.get("type")==101:
            raise PermissionError("Press the Hue Bridge link button and retry")
        raise RuntimeError("Hue pairing rejected")
    success=item.get("success")
    if not isinstance(success,dict):
        raise ValueError("Invalid Hue pairing response")
    key=success.get("username")
    if not isinstance(key,str) or not re.fullmatch(r"[A-Za-z0-9_-]{10,128}",key):
        raise ValueError("Invalid Hue application key")
    client=success.get("clientkey")
    if client is not None and (not isinstance(client,str) or not re.fullmatch(r"[a-fA-F0-9]{32}",client)):
        raise ValueError("Invalid Hue client key")
    return {"application_key":key,"client_key":client}

async def pair(address, certificate_sha256):
    ip=lan_ip(address)
    trust=fingerprint(certificate_sha256)
    async with ClientSession(timeout=ClientTimeout(total=8)) as session:
        async with session.post(f"https://{ip}/api",json={"devicetype":"christmas_control#local","generateclientkey":True},ssl=trust,allow_redirects=False) as response:
            response.raise_for_status()
            return pairing_result(await response.json())

async def inspect_certificate(address):
    """Unauthenticated TLS inspection only: never send HTTP or credentials."""
    import asyncio, ssl, hashlib
    ip=lan_ip(address)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname=False
    context.verify_mode=ssl.CERT_NONE
    reader,writer=await asyncio.wait_for(asyncio.open_connection(ip,443,ssl=context,server_hostname=ip,ssl_handshake_timeout=4),timeout=5)
    try:
        cert=writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
        if not cert: raise ValueError("No certificate")
        return hashlib.sha256(cert).hexdigest()
    finally:
        writer.close()
        try: await asyncio.wait_for(writer.wait_closed(),timeout=1)
        except (OSError,TimeoutError): pass
