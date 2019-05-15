import json
import time


from .merkletree import MerkleTree
from .lib.enums import LogLevel
from .transaction import Transaction
from .header import Header


class Block():

    def __init__(self, node, header, length, txns = [], whdrs = []):
        self.header = header

        self.length = length
        self.txns = txns
        self.weak_hdrs = whdrs # set of Header objects
        self.node = node # for logging purposes (not part of block)


    def generate_root_hash(self, items):
        tree = MerkleTree(items)
        return tree.get_root()


    def PoW(self):
        return Header.MAX_TARGET / self.header.target + (Header.MAX_TARGET / self.header.weak_target) * len(self.weak_hdrs)


    def get_ts(self):
        "Considers all weak headers' timestamps."
        sum_ts = self.header.timestamp
        sum_weight = 1
        ratio_wh = self.header.target / self.header.weak_target

        for whdr in self.weak_hdrs:
            sum_ts += ratio_wh * whdr.timestamp
            sum_weight += ratio_wh

        return sum_ts / sum_weight


    def print_block_info(self):
        self.node.log("Block[{}] Info:".format(self.length))
        self.node.log("PoW:                  " + str(self.PoW()), True)
        self.node.log("hash:                 " + self.header.hash, True)
        self.node.log("previous hash:        " + self.header.prev_hash, True)
        self.node.log("local time:           " + time.ctime(self.header.timestamp), True)
        self.node.log("nonce:                " + str(self.header.nonce), True)
        self.node.log("coinbase address:     " + self.header.coinbase[:32] + "..", True)
        self.node.log("target:               " + "{:064x}".format(self.header.target), True)
        self.node.log("length:               " + str(self.length), True)

        self.node.log("weak headers count:   " + str(len(self.weak_hdrs)), True)
        self.node.log("weak headers:         ", True, LogLevel.DEBUG)
        [[self.node.log(line, True, LogLevel.DEBUG) for line in str(wh).splitlines()] for wh in self.weak_hdrs]

        self.node.log("txns count:           " + str(len(self.txns)), True)
        self.node.log("txns:                 ", True, LogLevel.DEBUG)
        [[self.node.log(line, True, LogLevel.DEBUG) for line in str(tx).splitlines()] for tx in self.txns]


    def __str__(self):
        return self.to_json_str()


    def to_short_str(self):
        return "[{:>3d}] | H = {}, CB = {}, WHs = {:>2d}, TXNs = {:>2d}, target_s = {}, target_w = {}, PoW = {:>7.1f}|".format(
            self.length, self.header.hash[:16], self.header.coinbase[:16], len(self.weak_hdrs), len(self.txns),
            "{:064x}".format(self.header.target)[:16], "{:064x}".format(self.header.weak_target)[:16],  self.PoW()
        )


    def to_json(self):
        if not self.header.root:
            self.header.root = self.generate_root_hash(self.txns)
        if not self.header.whdrs_hash:
            self.header.whdrs_hash = self.node.blockchain.compute_hash_of_set(self.weak_hdrs)

        return {
            "header" : self.header.to_json(),
            "length" : self.length,
            "txns" : [tx.to_json() for tx in self.txns],
            "weak_hdrs" : [wh.to_json() for wh in self.weak_hdrs],
        }


    def to_json_str(self):
        return json.dumps(self.to_json(), indent=4)


    @classmethod
    def from_json_str(cls, node, json_string):
        j = json.loads(json_string)
        return Block.from_json(node, j)


    @classmethod
    def from_json(cls, node, j):
        return cls(node,  Header.from_json(j.get("header")), j.get("length"),
            [ Transaction.from_json(tx) for tx in j.get("txns")],
            [ Header.from_json(wh) for wh in j.get("weak_hdrs")]
        )
