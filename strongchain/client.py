
import ecdsa
import time
from numpy import mean, std

from .transaction import Transaction
from .lib.enums import LogLevel


class TxStatus:
    def __init__(self, tx, mined = False):
        self.tx = tx
        self.mined = mined
        self.block_len = None

class Client:

    def __init__(self, vk, sk, node):
        self.vk = vk
        self.sk = sk
        self.node = node
        self.all_txns_made = {} # contains entries mapping hash => TxStatus
        print("Log file of our node: " + node.get_log_filename())


    def serve_loop(self):

        self._wait_on_download_of_blockchain() # wait on dowload of blockchain

        while True:
            cmd = input("> ")
            cmd = cmd.strip()
            self._check_mined_txns()

            if cmd in [ "help", "h"]:
                self._print_help()

            elif cmd == '':
                continue

            elif cmd in ["exit", "quit"]:
                break

            elif cmd == "txns":
                self._cmd_txns()

            elif cmd == "whdrs":
                print("Current weak headers from node's cache:")
                [print(wh) for wh in self.node.blockchain.whdrs_cache.values()]

            elif cmd == "chain":
                mainchain = self.node.blockchain.get_mainchain()

                print("\nLength: \t{}".format(self.node.blockchain.tip_block.length))
                print("Chain PoW: \t{:>.2f}".format(self.node.blockchain.chainPoW()))
                print("Avg. whdrs:\t{:>.2f}".format(mean([len(block.weak_hdrs) for block in mainchain])))
                print("Stdev. whdrs:\t{:>.2f}".format(std([len(block.weak_hdrs) for block in mainchain])))
                print()
                print("Blocks:")
                [ print(block.to_short_str()) for block in mainchain]

            elif cmd in ["address", "addr"]:
                print("My address is: ", self.vk)

            elif cmd == "balance":
                print("My balance is:", self.node.bm.balances[self.vk])

            elif cmd == "balances":
                print("Balances of all accounts:")
                for addr in self.node.bm.balances:
                    me_flag = "(me)" if addr == self.vk else ""
                    print("\t{} : {} {}".format(addr, self.node.bm.balances[addr], me_flag))

            elif cmd == "stats":
                self._cmd_stats()

            elif cmd.strip().startswith("block "):
                if not self._cmd_block(cmd):
                    continue

            elif cmd.strip().startswith("send "):
                if not self._cmd_transfer(cmd):
                    continue

            elif cmd.strip().startswith("verbose"):
                if not self._cmd_verbose(cmd):
                    continue

            else:
                print("Unknown command.")


    def _wait_on_download_of_blockchain(self):
        print("Syncing blockchain...")
        while not self.node.blockchain_downloaded_event.is_set():
            time.sleep(0.1)
        print("Blockchain synced.")


    def _check_mined_txns(self):
        'Update status of all transactions that were mined already.'

        while not self.node.q_client_txns_mined.empty():
            tx = self.node.q_client_txns_mined.get()

            if tx.hash in self.all_txns_made:
                self.all_txns_made[tx.hash].mined = True
                self.all_txns_made[tx.hash].block_len = self.node.blockchain.get_blocklen_of_mined_tx(tx)


    def _cmd_stats(self):
        mainchain = self.node.blockchain.get_mainchain()
        cnt_strong = dict()
        cnt_weak = dict()

        for vk in self.node.bm.balances:
            cnt_strong[vk] = cnt_weak[vk] = 0

        for b in mainchain:
            if 1 == b.length: # skip genesis
                continue

            cnt_strong[b.header.coinbase] += 1
            for wh in b.weak_hdrs:
                cnt_weak[wh.coinbase] += 1

        print("\nStrong block statistics:")
        for vk in cnt_strong:
            me_flag = "(me)" if vk == self.vk else ""
            print("{}: {} {}".format(vk[:32], cnt_strong[vk], me_flag))

        print("\nWeak headers's statistics:")
        for vk in cnt_weak:
            me_flag = "(me)" if vk == self.vk else ""
            print("{}: {} {}".format(vk[:32], cnt_weak[vk], me_flag))


    def _cmd_txns(self):
        print("History of my transactions:")
        for i, txStatus in enumerate(self.all_txns_made.values()):
            print("Tx[{}] = {} | Mined = {} | Block.len = {}".format(i, str(txStatus.tx), txStatus.mined, txStatus.block_len))


    def _cmd_verbose(self, cmd):
        tokens = cmd.split()
        if 1 == len(tokens):
            self.node.log_level = LogLevel.DEBUG
        elif 2 == len(tokens) and tokens[1] in ["on", "off"]:
            self.node.log_level =  LogLevel.DEBUG if "on" == tokens[1] else LogLevel.INFO
        else:
            print("[Error]: Wrong argument. Only \"on\" and \"off\" are supported.")
            return False

        return True


    def _cmd_block(self, cmd):
        tokens = [i.strip() for i in cmd[6:].split(" ")]
        if 1 != len(tokens):
            print("[Error]: Wrong number of arguments.")
            return False

        try:
            int(tokens[0])
        except ValueError:
            print("[Error]: argument length must be a number.")
            return False

        block = self.node.blockchain.get_block_by_length(int(tokens[0]))
        if not block:
            print("[Error]: Non existing block.")
            return False

        print(str(block))
        return True


    def _cmd_transfer(self, cmd):
        tokens = [i.strip() for i in cmd[5:].split(",")]
        if tokens[0] not in self.node.bm.balances:
            print("[Error]: Non existing address.")
            return False

        amount = None
        try:
            amount = float(tokens[1])
        except ValueError:
            print("[Error]: Amount must be a number.")
            return False

        if amount > self.node.bm.balances[self.vk]:
            print("[Error]: Insufficient funds on my account.")
            return False


        comment = ','.join(tokens[2:]) if len(tokens) >= 3 else ''
        tx = Transaction(self.vk, tokens[0], amount, None, comment)
        if tx.hash in self.all_txns_made:
            print("[Error]: Attempt for duplicate transaction.")
            return False

        sk_key = ecdsa.SigningKey.from_string(bytes.fromhex(self.sk), curve = ecdsa.NIST192p)
        tx.signature = sk_key.sign(tx.hash.encode('utf-8')).hex()

        self.node.q_txns_from_client.put(tx)
        self.all_txns_made[tx.hash] = TxStatus(tx)
        print("[Info]: Transaction enqued.")

        return True


    def _print_help(self):
        print()
        print("{:<36} {}".format("[chain]", "displays current blockchain"))
        print("{:<36} {}".format("[txns]", "displays all transactions made by this client"))
        print("{:<36} {}".format("[balance[s]]", "get my balance | all balances"))
        print("{:<36} {}".format("[address | addr]", "get my address"))
        print("{:<36} {}".format("[send RECEIVER, AMOUNT [, COMMENT]]", "sends crypto-tokens to RECEIVER, appending optional comment"))
        print("{:<36} {}".format("[block ID]", "displays info about block with length = ID"))
        print("{:<36} {}".format("[stats]", "displays statistics about miners"))
        print("{:<36} {}".format("[whdrs]", "displays current cache of weak headers"))
        print()
        print("{:<36} {}".format("[help | h]", "shows this help"))
        print("{:<36} {}".format("[verbose [on | off]]", "enables verbose at log file."))
        print("{:<36} {}".format("[exit | quit]", "ends operation of this node"))
        print()

