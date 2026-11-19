"""Local provider configuration. Never expose credentials through public views."""
import json
import os
import re
import tempfile
from pathlib import Path
from .common import lan_ip

def validate(data):
    if not isinstance(data,dict) or set(data)!={"version","hue","govee"} or data["version"]!=1:
        raise ValueError("Invalid provider configuration")
    for provider in ("hue","govee"):
        if not isinstance(data[provider],dict):
            raise ValueError("Invalid provider records")
        for identifier,record in data[provider].items():
            if not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}",identifier) or not isinstance(record,dict):
                raise ValueError("Invalid provider record")
            lan_ip(record.get("address"))
            allowed={"address","application_key","client_key","certificate_sha256"} if provider=="hue" else {"address"}
            if set(record)-allowed:
                raise ValueError("Unexpected provider fields")
            if provider=="hue":
                for key,pattern in (("application_key",r"[A-Za-z0-9_-]{10,128}"),("certificate_sha256",r"[a-fA-F0-9]{64}")):
                    if not isinstance(record.get(key),str) or not re.fullmatch(pattern,record[key]):
                        raise ValueError("Invalid Hue credentials")
                client=record.get("client_key")
                if client is not None and (not isinstance(client,str) or not re.fullmatch(r"[a-fA-F0-9]{32}",client)):
                    raise ValueError("Invalid Hue client key")
    return data

class ProviderStore:
    def __init__(self, directory="/data"):
        self.path=Path(directory)/"light-providers.json"

    def load(self):
        try:
            fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:
            return {"version":1,"hue":{},"govee":{}}
        with os.fdopen(fd,"r",encoding="utf-8") as stream:
            if os.fstat(stream.fileno()).st_mode & 0o077:
                raise PermissionError("Provider configuration permissions too broad")
            raw=stream.read(1048577)
            if len(raw)>1048576:
                raise ValueError("Provider configuration too large")
            return validate(json.loads(raw))

    def save(self,data):
        raw=json.dumps(validate(data),separators=(",",":"))
        if len(raw)>1048576:
            raise ValueError("Provider configuration too large")
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=self.path.parent,prefix=".providers-")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp,self.path)
            directory=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def public(self):
        data=self.load()
        return {provider:{identifier:{"address":record["address"],"configured":True} for identifier,record in data[provider].items()} for provider in ("hue","govee")}
