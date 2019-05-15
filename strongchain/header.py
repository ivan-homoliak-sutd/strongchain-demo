
import json
import hashlib

class Header:

    MAX_TARGET         = 0x000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    INIT_STRONG_TARGET = 0x0000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
    WEAK_TARGET_POWER  = 3      # on average, we should produce 2^3 weak headers per block

    def __init__(self, prev_hash, timestamp, nonce, root, whdrs_hash, cb, target):
        self.prev_hash = prev_hash
        self.timestamp = float(timestamp)
        self.nonce = int(nonce)
        self.root = root
        self.coinbase = cb # address of the miner who mined this block
        self.target = target # strong target

        # NOT PART OF HEADER
        self.whdrs_hash = whdrs_hash # this field should not be part of header (here is just for simplicity)


    @property
    def hash(self):
        return hashlib.sha256(
            (str(self.prev_hash) + str(self.timestamp) + str(self.nonce) + self.root + self.whdrs_hash + self.coinbase + str(self.target)).encode()
        ).hexdigest()

    @property
    def weak_target(self):
        return self.target << Header.WEAK_TARGET_POWER


    def compute_whdr_reward(self, strong_blk_reward):
        return strong_blk_reward * (self.target / self.weak_target)


    def to_json(self):
        return {
            'hash' : self.hash,
            'prev_hash' : self.prev_hash,
            'timestamp' : self.timestamp,
            'nonce' : self.nonce,
            'root' : self.root,
            'whdrs_hash' : self.whdrs_hash,
            'coinbase' : self.coinbase,
            'target' : self.target
        }

    def to_json_str(self, indent = True):
        return json.dumps(self.to_json(), indent = 4 if indent else None)


    @classmethod
    def from_json_str(cls, json_string):
        j = json.loads(json_string)
        return Header.from_json(j)

    @classmethod
    def from_json(cls, j):
        return cls(j.get("prev_hash"), j.get("timestamp"), j.get("nonce"), j.get("root"), j.get("whdrs_hash"), j.get("coinbase"), j.get("target"))


    def __str__(self):
        return self.to_json_str()
