import copy
import datetime
import hashlib
import random
import time
from numpy import mean, std

from .block import Block
from .header import Header
from .merkletree import MerkleTree
from .transaction import Transaction
from .lib.enums import LogLevel, MsgType, BlockValidationStatus as BlkValStatus

class Blockchain:

    GENESIS_PREV_HASH = '0' * 64
    GENESIS_TS = 1542696180
    GENESIS_CB = '0' * 96
    GENESIS_NONCE = 1111111
    GENESIS_LEN = 1

    BLOCKS_TO_CHECK_TARGET = 10 # after this number of blocks is target recomputed
    TIME_BETWEEN_BLOCKS = 3  # in seconds

    STRONG_BLOCK_REWARD = 10

    TIMESTAMP_RANGE = 3600

    def __init__(self, node):
        self.node = node
        self.all_blocks = {}
        self.whdrs_cache = {} # hash => Header() // serves just for mining
        self.times_of_blocks = [] # it is just an estimation; considers only blocks created since begining of this node
        self.tip_block = self._add_genesis_block()
        random.seed(node.get_log_filename())

        self.node.log("[Blockchain]: Ratio of weak/strong targets is {}".format(pow(2, Header.WEAK_TARGET_POWER)))
        self.node.log("[Blockchain]: Desired time between blocks is {}".format(Blockchain.TIME_BETWEEN_BLOCKS))
        self.node.log("[Blockchain]: Block reward {}".format(Blockchain.STRONG_BLOCK_REWARD))
        self.node.log("[Blockchain]: Weak header reward {}".format(Blockchain.STRONG_BLOCK_REWARD / pow(2, Header.WEAK_TARGET_POWER)))
        self.node.log("", True)


    def add_block(self, block):
        self.times_of_blocks.append(time.time())
        self.all_blocks[block.header.hash] = block


    def _add_genesis_block(self):
        txns = []
        root = MerkleTree.compute_root(txns)
        header = Header(Blockchain.GENESIS_PREV_HASH, Blockchain.GENESIS_TS, Blockchain.GENESIS_NONCE, root,
            Blockchain.GENESIS_PREV_HASH, Blockchain.GENESIS_CB, Header.INIT_STRONG_TARGET
        )
        genesis = Block(self.node, header, Blockchain.GENESIS_LEN, txns, [])
        # no checks are made for genesis
        self.add_block(genesis)
        return genesis


    def get_expected_time_of_arrival(self, header):
        return self.all_blocks[header.prev_hash].get_ts() + Blockchain.TIME_BETWEEN_BLOCKS


    def validate_block(self, block):

        # check whether we already do not have it
        if block.header.hash in self.all_blocks:
            return BlkValStatus.EXISTING_BLOCK

        # check whether block's parent exists
        if block.header.prev_hash not in self.all_blocks:
            return BlkValStatus.NON_EXISTING_PRED

        # check integrity of txns
        tree = MerkleTree(block.txns)
        if block.header.root != tree.get_root():
            return BlkValStatus.TXNS_INTEGRITY

        # check integrity of whdrs
        if block.header.whdrs_hash != self.compute_hash_of_set(block.weak_hdrs):
            return BlkValStatus.WHDRS_INTEGRITY

        # check strong target
        strong_target = self.get_next_strong_target(self.all_blocks[block.header.prev_hash], LogLevel.NONE)
        if block.header.target != strong_target:
            return BlkValStatus.TARGET_VALUE

        if int(block.header.hash, 16) >= strong_target:
            return BlkValStatus.STRONG_TARGET_POW

        # check timestamp
        if self.all_blocks[block.header.prev_hash].header.prev_hash != Blockchain.GENESIS_PREV_HASH: # skip genesis
            if abs(self.get_expected_time_of_arrival(block.header) - block.header.timestamp) > self.TIMESTAMP_RANGE:
                return BlkValStatus.HDR_TIMESTAMP

        # check weak headers
        for wh in block.weak_hdrs:

            status = self.validate_weak_header(wh, block.header)
            if BlkValStatus.WHDR_OK != status:
                return status

        return BlkValStatus.OK


    def validate_weak_header(self, wh, parent_hdr):

        # weak targets
        if wh.target != parent_hdr.target:
            return BlkValStatus.WHDR_TARGET_VALUE

        if int(wh.hash, 16) >= wh.weak_target:
            return BlkValStatus.WHDR_TARGET_POW

        # binding
        if wh.prev_hash != parent_hdr.prev_hash:
            return BlkValStatus.WHDR_PREV_HASH

        # timestamp
        if self.all_blocks[wh.prev_hash].header.prev_hash != Blockchain.GENESIS_PREV_HASH: # skip genesis
            if abs(self.get_expected_time_of_arrival(wh) - wh.timestamp) > self.TIMESTAMP_RANGE:
                return BlkValStatus.WHDR_TIMESTAMP

        return BlkValStatus.WHDR_OK


    def chainPoW(self, block=None):
        """
            If block is None, then use tip_block of mainchain.
            TODO: It could be more optimal and go until fork only. Now it goes until genesis.
        """
        cur_pow = 0
        cur_hash = block.header.hash if block else self.tip_block.header.hash

        if not cur_hash in self.all_blocks.keys():
            return block.PoW()

        while cur_hash != self.GENESIS_PREV_HASH:
            cur_block = self.all_blocks[cur_hash]
            cur_pow += cur_block.PoW()
            cur_hash = cur_block.header.prev_hash

        return cur_pow


    def current_whdrs_PoW(self):
        return (Header.MAX_TARGET / self.tip_block.header.weak_target) * len(self.whdrs_cache)


    def get_next_strong_target(self, prev_block, _log_level = LogLevel.INFO):
        """
            Every BLOCKS_TO_CHECK_TARGET, recompute strong target of the next block based on avg. time to mine block.
        """
        if  prev_block.header.prev_hash != Blockchain.GENESIS_PREV_HASH and 1 == (prev_block.length) % (Blockchain.BLOCKS_TO_CHECK_TARGET):
            self.node.log(20 * '=' + " Adjusting strong target " + 20 * '=', log_level=_log_level)

            block_window = Blockchain.BLOCKS_TO_CHECK_TARGET
            # omit genesis block that has old fixed timestamp
            if Blockchain.BLOCKS_TO_CHECK_TARGET + 1 == prev_block.length:
                block_window -= 1

            retro_block = prev_block
            for i in range(block_window):
                retro_block = self.all_blocks[retro_block.header.prev_hash]

            ts_diff = prev_block.get_ts() - retro_block.get_ts()
            ratio   = ts_diff / (block_window * Blockchain.TIME_BETWEEN_BLOCKS)

            new_target = int(prev_block.header.target * ratio)
            self.node.log("Time for mining {} blocks is {:>2.2f}, i.e. {:>2.3f} per block.".format(
                block_window, ts_diff, ts_diff / block_window),
                log_level=_log_level
            )
            self.node.log("Updated strong target from {}.. to {}.. ".format(
                    "{:064x}".format(prev_block.header.target)[:16], "{:064x}".format(new_target)[:16]
                ), log_level=_log_level
            )
            self.node.log(65 * '=', log_level=_log_level)
            return new_target
        else:
            return prev_block.header.target # just inherit target from the previous block


    def get_balance(self, address):
        'This is should be called only when a new node starts, as it is expensive.'

        blk = self.tip_block
        total_funds = 0

        while blk.header.prev_hash != self.GENESIS_PREV_HASH:
            # incomming txns
            for incomming_txn in (tx for tx in blk.txns if tx.receiver == address):
                total_funds += incomming_txn.amount

            # outgoing txns
            for outgoing_txn in (tx for tx in blk.txns if tx.sender == address):
                total_funds -= outgoing_txn.amount

            # rewards for strong block
            if blk.header.coinbase == address:
                total_funds += self.STRONG_BLOCK_REWARD

            # rewards for weak headers
            whdrs = [wh for wh in blk.weak_hdrs if wh.coinbase == address]
            total_funds += blk.header.compute_whdr_reward(Blockchain.STRONG_BLOCK_REWARD) * len(whdrs)

            blk = self.all_blocks[blk.header.prev_hash]

        return total_funds


    def mine_next_block(self, coinbase, txns, stop_event, broadcast_whdrs=True):

        root = MerkleTree.compute_root(txns) # txns root
        ts = str(time.time())
        prev_hash = self.tip_block.header.hash
        whdrs_hash = self.compute_hash_of_set(self.whdrs_cache.values())
        strong_target = self.get_next_strong_target(self.tip_block)

        while not stop_event.is_set():
            time.sleep(0.0001)

            nonce = str(random.randint(0, 10000000))
            new_header = Header(prev_hash, ts, nonce, root, whdrs_hash, coinbase, strong_target)
            h = new_header.hash

            if int(h, 16) < new_header.target:
                self.node.log(66 * '+')
                self.node.log(20 * '+' + " Mined a new strong block " + 20 * '+')
                self.node.log(66 * '+')
                new_block =  Block(self.node, new_header, self.tip_block.length + 1,
                    [Transaction.from_json_str(tx) for tx in txns], self.whdrs_cache.values()
                )
                new_block.print_block_info()
                self.whdrs_cache = {}
                return new_block

            if int(h, 16) < new_header.weak_target:
                if not h in self.whdrs_cache:
                    self.whdrs_cache[h] = new_header
                    self.node.log(20 * '+' + " Mined a new weak header " + 20 * '+')
                    [self.node.log(line, True, LogLevel.DEBUG) for line in str(self.whdrs_cache[h]).splitlines()]
                    if broadcast_whdrs:
                        self.node.broadcast(MsgType.WEAK_HEADER_MINED, self.whdrs_cache[h])
                    whdrs_hash = self.compute_hash_of_set(self.whdrs_cache.values())

            if not self.node.q_strong.empty():
                return None

            while not self.node.q_weak.empty():
                rcv_whdr = self.node.q_weak.get()
                # self.node.log(20 * '-' + " Weak header received " + 20 * '-')
                [self.node.log(line, True, LogLevel.DEBUG) for line in str(rcv_whdr).splitlines()]

                if rcv_whdr.hash in self.whdrs_cache:
                    self.node.log("... already existing weak header with H = {}.".format(rcv_whdr.hash), True)
                    continue

                status = self.validate_weak_header(rcv_whdr, new_header)
                if BlkValStatus.WHDR_OK != status:
                    self.node.log("... invalid weak header, error '{}'".format(status.name), True)
                    continue

                self.whdrs_cache[rcv_whdr.hash] = rcv_whdr
                whdrs_hash = self.compute_hash_of_set(self.whdrs_cache.values())


    def compute_hash_of_set(self, set_of_serializable):
        if 0 == len(set_of_serializable):
            return 64 * '0'

        s = '|'.join([ item.to_json_str() for item in set_of_serializable])
        return hashlib.sha256(s.encode()).hexdigest()


    def get_blocklen_of_mined_tx(self, tx):

        cur_block = self.tip_block
        while cur_block.header.hash != self.GENESIS_PREV_HASH:
            if tx.hash in (t.hash for t in cur_block.txns):
                return cur_block.length

            cur_block = self.all_blocks[cur_block.header.prev_hash]

        return None


    def get_chain(self, tip_hash):
        cur_hash = tip_hash
        chain = []

        if not cur_hash in self.all_blocks.keys():
            return None

        while cur_hash != self.GENESIS_PREV_HASH:
            cur_block = self.all_blocks[cur_hash]
            chain.append(cur_block)
            cur_hash = cur_block.header.prev_hash

        return chain[::-1]


    def get_mainchain(self):
        return self.get_chain(self.tip_block.header.hash)


    def get_block_by_length(self, length):
        if length > self.tip_block.length or length < 1:
            return None

        chain = self.get_mainchain()
        return chain[length - 1]


    def get_time_among_blocks(self):

        diffs = []
        for i, t in enumerate(self.times_of_blocks):
            if i != 0:
                diffs.append(t - self.times_of_blocks[i - 1])

        return mean(diffs), std(diffs)


    def print_chain(self, last_n=10):
        'Print last_n blocks of chain.'

        self.node.log(20 * '=' + " Mainchain - Last {} blocks ".format(last_n) + 20 * '=', log_level=LogLevel.DEBUG)
        self.node.log("Length: {:>3d}".format(self.tip_block.length), True, log_level=LogLevel.DEBUG)
        self.node.log("PoW of Chain: {}".format(self.chainPoW(self.tip_block)), True, log_level=LogLevel.DEBUG)
        self.node.log("Time among blocks: {:>2.2f} (+-{:>2.2f})".format(*self.get_time_among_blocks()), True, log_level=LogLevel.DEBUG)

        for block in self.get_mainchain()[-last_n:]:
            b_str = block.to_short_str()
            self.node.log(b_str, True, log_level=LogLevel.DEBUG)

        self.node.log(68 * '=', True, log_level=LogLevel.DEBUG)
