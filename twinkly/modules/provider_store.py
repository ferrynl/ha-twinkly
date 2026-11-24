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
            allowed={"address","application_key","client_key","certificate_sha256"} if provider=="hue" else {"address", "sku"}
            if set(record)-allowed:
                raise ValueError("Unexpected provider fields")
            if provider == "govee" and "sku" in record and (not isinstance(record["sku"], str)
                    or not 1 <= len(record["sku"]) <= 64):
                raise ValueError("Invalid Govee model")
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
        self.groups_path=Path(directory)/"lighting-groups.json"
        self.scenes_path=Path(directory)/"lighting-scenes.json"

    @staticmethod
    def read(path, default, max_size=1_048_576):
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:
            return default
        with os.fdopen(fd,"r",encoding="utf-8") as stream:
            if os.fstat(stream.fileno()).st_mode & 0o077:
                raise PermissionError("Provider configuration permissions too broad")
            raw=stream.read(max_size + 1)
            if len(raw)>max_size:
                raise ValueError("Provider configuration too large")
            return json.loads(raw)

    def load(self):
        return validate(self.read(self.path, {"version":1,"hue":{},"govee":{}}))

    def load_groups(self):
        groups = self.read(self.groups_path, {})
        if not isinstance(groups, dict) or any(
            not re.fullmatch(r"[a-f0-9]{32}", key)
            or not isinstance(group, dict)
            or not isinstance(group.get("name"), str)
            or not isinstance(group.get("members"), list)
            or any(not isinstance(member, str) for member in group["members"])
            for key, group in groups.items()
        ):
            raise ValueError("Invalid lighting groups")
        return groups

    def save_groups(self, groups):
        self.write(self.groups_path, groups)

    def load_scenes(self):
        scenes = self.read(self.scenes_path, {})
        if not isinstance(scenes, dict) or any(
            not re.fullmatch(r"[a-f0-9]{32}", key)
            or not isinstance(scene, dict)
            or not isinstance(scene.get("name"), str)
            or not isinstance(scene.get("group"), str)
            or type(scene.get("on")) is not bool
            for key, scene in scenes.items()
        ):
            raise ValueError("Invalid lighting scenes")
        return scenes

    def save_scenes(self, scenes):
        self.write(self.scenes_path, scenes)

    def save(self,data):
        self.write(self.path, validate(data))

    @staticmethod
    def write(path, data, max_size=1_048_576):
        raw=json.dumps(data,separators=(",",":"))
        if len(raw)>max_size:
            raise ValueError("Provider configuration too large")
        path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=".providers-")
        try:
            with os.fdopen(fd,"w",encoding="utf-8") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp,path)
            directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
            try: os.fsync(directory)
            finally: os.close(directory)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

    def public(self):
        data=self.load()
        return {provider:{identifier:{"address":record["address"],"configured":True} for identifier,record in data[provider].items()} for provider in ("hue","govee")}
