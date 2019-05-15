import json


class NodeConf:
    def __init__(self, port, address, vk):
        self.port = port
        self.address = address
        self.vk = vk


    def __eq__(self, other):
        return self.port == other.port \
            and self.address == other.address \
            and self.vk == other.vk


    @classmethod
    def from_json_str(cls, json_string):
        j = json.loads(json_string)
        return cls(j.get("port"), j.get("address"), j.get("vk"))


    def to_json(self):
        return {
            "port" : self.port,
            "address" : self.address,
            "vk" : self.vk
        }


    def to_json_str(self, indent = 4):
        return json.dumps(self.to_json(), indent = indent)


    def __str__(self):
        return self.to_json_str(indent = None)
