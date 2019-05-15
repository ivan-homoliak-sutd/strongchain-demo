import os
import json
import copy
import time
import socket
import threading

from .block import Block
from .header import Header
from .blockchain import Blockchain, MsgType
from .transaction import Transaction
from .lib.queue import Queue
from .lib.enums  import LogLevel, MsgType, BlockValidationStatus as BlkValStatus
from .lib.nodeconfig import NodeConf


class Node:
    LOG_DIR = os.path.sep.join([".", "logs"])

    MAX_BUF_SIZE = pow(2, 21)

    def __init__(self, node_id, conf, priv_key, peers = None, log_level=LogLevel.INFO):

        self.id = node_id
        self.log_level = log_level
        self.log_file = self._init_log_file()

        self.pub_key = conf.vk
        self.priv_key = priv_key
        self.address = conf.address
        self.port = conf.port
        self.blockchain = Blockchain(self)  # node's blockchain
        self.bm = BalanceModel(self, peers)
        self.peers = peers
        self.txns_to_mine = set() # current txns to mine on (in json string format due to imutability)
        self.mined_client_txns = set() # txns sent by our client (in json string format due to imutability)

        # thread-safe queues for client VS mining thread
        self.q_client_txns_mined = Queue()
        self.q_txns_from_client = Queue()
        # thread-safe queues for listening VS mining thread
        self.q_strong = Queue()
        self.q_weak = Queue()
        self.q_txns_from_others = Queue()

        # events
        self.stop_mining_event = threading.Event()
        self.stop_listening_event = threading.Event()
        self.blockchain_downloaded_event = threading.Event()


    def _wait_on_download_of_blockchain(self):
        while not self.blockchain_downloaded_event.is_set():
            time.sleep(0.1)


    def mining_thread(self):
        self.log('Mining thread started')

        self._wait_on_download_of_blockchain()

        while True:

            self._preupdate_mined_txns()

            # start mining
            mined_block = self.blockchain.mine_next_block(self.pub_key, self.txns_to_mine, self.stop_mining_event)
            if self.stop_mining_event.is_set(): return

            if mined_block is not None:
                # we mined a new block
                self.blockchain.add_block(mined_block)
                self.blockchain.tip_block = mined_block
                self.broadcast(MsgType.STRONG_BLOCK_MINED, mined_block)
                self._update_txns_to_mine(mined_block)
                self.bm.update_balances(mined_block)
            else:
                # handle received new block
                rcv_block = self.q_strong.get()
                rcv_block.print_block_info()
                if not self._validate_recv_block(rcv_block):
                    continue

                self._add_recv_block(rcv_block)
                self.blockchain.whdrs_cache = {}
                self._update_txns_to_mine(rcv_block)

            self.blockchain.print_chain()
            self.bm.print_balances(LogLevel.DEBUG)


    def listening_thread(self):
        self.log("Listening thread started")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('localhost', self.port,))
        sock.settimeout(1)
        msg_str = None

        self.download_blockchain(sock)
        self.blockchain_downloaded_event.set() # inform mining thread to start
        self.log('=' * 80)
        self.log("[Listening thread]: >>> blockchain synced <<<")
        self.log('=' * 80)

        while not self.stop_listening_event.is_set():
            try:
                msg_str, addr = sock.recvfrom(Node.MAX_BUF_SIZE)
            except socket.timeout:
                continue

            msg = json.loads(msg_str)

            if  MsgType.WEAK_HEADER_MINED == msg['type']:
                self.log("[Listening thread]: Received weak header from " + msg['from'][:16])
                self.q_weak.put(Header.from_json_str(msg['data']))

            elif MsgType.STRONG_BLOCK_MINED == msg['type']:
                self.log("[Listening thread]: Received strong block from " + msg['from'][:16])
                self.q_strong.put(Block.from_json_str(self, msg['data']))

            elif MsgType.TRANSACTION == msg['type']:
                self.log("[Listening thread]: Received new TX message from " + msg['from'][:16])
                self.q_txns_from_others.put(Transaction.from_json_str(msg['data']))

            elif MsgType.GET_BLOCK == msg['type']:
                self.log("[Listening thread]: Received request for block[{}] from {}.".format(msg['data'], msg['from'][:16]))
                try:
                    int(msg['data'])
                except ValueError:
                    self.log("[Listening thread]: Block lenght '{}' is not an integer, skipping.".format( msg['data']))
                    continue

                ret_block = self.blockchain.get_block_by_length(int(msg['data']))
                reply = {
                    'type': MsgType.BLOCK, 'from': self.pub_key,
                    'data': ret_block.to_json_str() if ret_block else None
                }
                self.send_message(reply, self.find_peer_by_vk(msg['from']))

            elif MsgType.BLOCK == msg['type']:
                self.log("[Listening thread]: Unexpected block message received from {}, skipping ".format(msg['from'][:16]))
                continue

            elif MsgType.NEW_PEER == msg['type']:
                self.log("[Listening thread]: Received new peer message " + msg['from'][:16])
                peer = self._add_new_peer(msg["data"])
                if not peer:
                    continue # error occured

                self.log("[Listening thread]: Sending new peer acknowledgement to " + msg['from'][:16])
                self.send_message({'type': MsgType.NEW_PEER_ACK, 'from': self.pub_key, 'data': None}, peer)

            else:
                self.log("[Listening thread]: Invalid message received. Type = " + msg['type'])


    def _preupdate_mined_txns(self):

        # add txns from our client
        while not self.q_txns_from_client.empty():
            tx = self.q_txns_from_client.get()
            self.txns_to_mine.add(tx.to_json_str())
            self.mined_client_txns.add(tx.to_json_str())
            self.broadcast(MsgType.TRANSACTION, tx)

        # add txns broadcasted by other nodes (we do not relay them)
        while not self.q_txns_from_others.empty():
            tx = self.q_txns_from_others.get()
            self.txns_to_mine.add(tx.to_json_str())

        # filter out invalid Txns (check amounts after block, duplicates, and signatures)
        self._filter_out_invalid_txns()


    def find_peer_by_vk(self, vk):
        for p in self.peers:
            if p.vk == vk:
                return p
        return None

    def _add_new_peer(self, data_str):
        nc = NodeConf.from_json_str(data_str)
        try:
            int(nc.port)
        except ValueError:
            self.log("[Listening thread]: Port '{}' is not an integer, skipping.".format(nc.port))
            return None

        if nc in self.peers:
            return self.peers[self.peers.index(nc)]
        else:
            self.log("[Listening thread]: adding a new peer {}".format(str(nc)))
            self.peers.append(nc)
            self.bm.balances[nc.vk] = 0
            return nc


    def download_blockchain(self, sock):
        msg = msg_str = None
        online_peers = []

        # inform peers about us and select some online peer (i.e., the last)
        for p in self.peers:
            my_conf = NodeConf(self.port, self.address, self.pub_key)
            self.send_message({'type': MsgType.NEW_PEER, 'from': self.pub_key, 'data': my_conf.to_json_str()}, p)

            try:
                # skip other types of messages if any
                while True:
                    msg_str, addr = sock.recvfrom(Node.MAX_BUF_SIZE)
                    msg = json.loads(msg_str)
                    if  MsgType.NEW_PEER_ACK == msg['type']:
                        break
            except socket.timeout: # peer is unavailable
                continue

            self.log("[Listening thread]: received acknowledgement of new peer from {}..".format(msg["from"][:16]))
            online_peers.append(self.find_peer_by_vk(msg["from"]))

        # no peers are online, so we assume that we are the first
        if 0 == len(online_peers):
            self.log("[Listening thread]: No peers are online. We are the first.")
            return

        sock.settimeout(2)
        self.log("[Listening thread]: peers {} are online.".format(str([p.vk[:16] for p in online_peers])))

        # ask for all blocks - balance block requests among all online peers
        i = 0
        while not self.stop_listening_event.is_set():
            i += 1

            requested_id = self.blockchain.tip_block.length + 1
            self.send_message({'type': MsgType.GET_BLOCK, 'from': self.pub_key, 'data': requested_id}, online_peers[i % len(online_peers)])
            try:
                self.log("[Listening thread]: sending get block[{}] request.".format(requested_id))
                msg_str, addr = sock.recvfrom(Node.MAX_BUF_SIZE)
            except socket.timeout:
                self.log("[Listening thread]: re-sending get block[{}] request.".format(requested_id))
                continue

            msg = json.loads(msg_str)

            if  MsgType.BLOCK == msg['type']:
                # we reached the last block of the peer that we are syncing from
                if None == msg['data']:
                    self.log("Peer {} does not have block[{}].".format(i % len(online_peers), requested_id), True)
                    break

                self.log("[Listening thread]: Received block[{}] from {}..".format(requested_id, msg['from'][:16]) )
                rcv_block = Block.from_json_str(self, msg['data'])
                rcv_block.print_block_info()

                self._validate_recv_block(rcv_block)
                self._add_recv_block(rcv_block)

            else:
                continue # ignore all other messages when syncing blockchain

        sock.settimeout(1)


    def broadcast(self, msg_type, obj):

        msg = {'type': msg_type, 'from': self.pub_key, 'data': obj.to_json_str()}
        for peer in self.peers:
            self.send_message(msg, peer)


    def send_message(self, msg, peer):
        data_sent = 0

        addr = (peer.address, peer.port)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            data_sent = sock.sendto(json.dumps(msg).encode(), addr)
        except Exception as e:
            self.log("[ERROR] when sending message with type {} to {}.".format(msg['type'], str(addr)), log_level=LogLevel.ERROR)
            self.log("{}".format(str(e)), True, log_level=LogLevel.ERROR)
        finally:
            sock.close()

        return data_sent


    def _validate_recv_block(self, rcv_block):

        status = self.blockchain.validate_block(rcv_block)
        if  BlkValStatus.OK != status:
            self.log( "[!!!] Validation of strong or weak headers failed with '{}' [!!!]".format(status.name))
            return False

        if not self._validate_txns_of_recv_block(rcv_block):
            self.log("[!!!] Validation of transactions failed [!!!]")
            return False

        return True

    def _add_recv_block(self, rcv_block):

        self.blockchain.add_block(rcv_block)

        if rcv_block.header.prev_hash != self.blockchain.tip_block.header.hash:
            self.log("[XXX] adding block to another chain [XXX]")

            # if this chain is "stronger" than the current chain, switch to it
            if self.blockchain.chainPoW(rcv_block) > self.blockchain.chainPoW(self.blockchain.tip_block) + self.blockchain.current_whdrs_PoW():
                self.log("[FORK] switching to stronger chain [FORK]")
                self.blockchain.tip_block = rcv_block
                self.bm.rebuild_balances_after_fork()
        else:
            self.log("updating my own chain", True)
            self.blockchain.tip_block = rcv_block
            self.bm.update_balances(rcv_block)


    def _validate_txns_of_recv_block(self, rcv_block, other_bm=None):
        "other_bm: serves selfish miner who wants to check balances of honest chain"

        if len(rcv_block.txns) == 0: return True

        # scan for duplicate Txns in previous blocks
        relevant_chain = self.blockchain.get_chain(rcv_block.header.prev_hash)
        if None == relevant_chain:
            return False

        for tx in rcv_block.txns:
            for blk in relevant_chain:
                if  tx.hash in (t.hash for t in blk.txns):
                    self.log("[ERROR]: Invalid block - duplicate Tx found", True)
                    return False

        # check each transaction's signature & balance
        bm = self.bm if not other_bm else other_bm
        if not bm.check_balances_and_sigs(rcv_block.txns):
            self.log('received block is invalid')
            return False

        return True


    def _filter_out_invalid_txns(self):
        if len(self.txns_to_mine) == 0:
            return

        # filter out duplicates based on history of blockchain
        main_chain = self.blockchain.get_mainchain()
        for blk in main_chain:
            for tx in blk.txns:
                if tx.to_json_str() in self.txns_to_mine:
                    self.txns_to_mine.remove(tx.to_json_str())

        # filter out txns with invalid sigantures and amounts
        self.txns_to_mine = self.bm.filter_out_invalid_txns(self.txns_to_mine)


    def _update_txns_to_mine(self, new_valid_block):
        'Update our client and remove already mined txns from our pool.'

        # inform client if any of its txns were mined
        for tx in new_valid_block.txns:
            if tx.to_json_str() in self.mined_client_txns:
                self.q_client_txns_mined.put(tx)
                self.mined_client_txns.remove(tx.to_json_str())

        # remove already mined txns from our pool
        self.txns_to_mine.difference_update([tx.to_json_str() for tx in new_valid_block.txns])


    def _init_log_file(self):
        return open(self.get_log_filename(), 'w', buffering = 1)


    def log(self, msg, stick_to_previous=False, log_level=LogLevel.INFO):

        if log_level <= self.log_level:

            t = time.ctime()
            if stick_to_previous:
                self.log_file.write("{} {}\n".format(' ' * (len(t) + 3), msg))
            else:
                self.log_file.write("[{}]: {}\n".format(t, msg))



    def get_log_filename(self):
        return os.path.join(self.LOG_DIR, "node-{}.log".format(self.id))


class BalanceModel:

    def __init__(self, node, peers):
        self.node = node # for logging purposes
        self.balances = self._init_balances(peers) # pub_key => amount //  account balance model


    def _init_balances(self, peers):
        balances = {}
        for peer in peers:
            balances[peer.vk] = 0

        # balance of the current node
        balances[self.node.pub_key] = 0
        return balances


    def update_balances(self, new_block):
        # resolve transactions
        for tx in new_block.txns:
            self.balances[tx.sender] -= tx.amount
            self.balances[tx.receiver] += tx.amount

        # resolve rewards for strong and weak blocks
        self.balances[new_block.header.coinbase] += Blockchain.STRONG_BLOCK_REWARD
        for whdr in new_block.weak_hdrs:
            self.balances[whdr.coinbase] += whdr.compute_whdr_reward(Blockchain.STRONG_BLOCK_REWARD)


    def check_balances_and_sigs(self, txns):

        temp_balances = copy.deepcopy(self.balances)

        for tx in txns:

            if tx.amount < 0:
                self.node.log("Invalid Tx: negative value in amount | Tx = " + tx.to_json_str(), True)
                return False

            if not tx.validate_sig():
                self.node.log("Validation of signature failed | Tx = " + tx.to_json_str(), True)
                return False

            temp_balances[tx.sender] -= tx.amount
            if temp_balances[tx.sender] < 0:
                self.node.log("Not enough balance for sender {} | Tx = {}".format(tx.sender, tx.to_json_str()), True)
                return False

            temp_balances[tx.receiver] += tx.amount

        return True

    def filter_out_invalid_txns(self, txns):
        'The validation is dependent on the order of elements in the set.'
        temp_balances = copy.deepcopy(self.balances)
        valid_txns = set()

        for tx_str in txns:
            tx = Transaction.from_json_str(tx_str)
            if tx.amount < 0:
                continue

            if not tx.validate_sig():
                continue

            temp_balances[tx.sender] -= tx.amount
            if temp_balances[tx.sender] < 0:
                continue

            temp_balances[tx.receiver] += tx.amount
            valid_txns.add(tx_str)

        return valid_txns


    def rebuild_balances_after_fork(self):
        """TODO: Could be optimized to revert txns backwards - until a block when fork happened.
            Now, it scans the whole blockchain in the same way as a new node were to compute balances.
        """
        for addr in self.balances:
            self.balances[addr] = self.node.blockchain.get_balance(addr)


    def print_balances(self, _log_level):
        self.node.log(20 * '=' +  " balances " + 20 * '=', log_level=_log_level)
        for addr in self.balances:
            self.node.log("\t{} : {}".format(addr, self.balances[addr]), True, _log_level)
        self.node.log(50 * '=', True, _log_level)

