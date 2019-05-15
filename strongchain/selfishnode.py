
import copy

from .node import Node, BalanceModel
from .lib.enums  import LogLevel, MsgType, BlockValidationStatus as BlkValStatus, SelfishMState as SMState
from .header import Header

class SelfishNode(Node):

    # represents the ratio of received block's POW (only for strong target), with which (and with the lower values) we reveal our secret chain
    RATIO_TO_OVERRIDE = 1/8

    def __init__(self, node_id, conf, priv_key, peers = None, log_level=LogLevel.INFO):
        Node.__init__(self, node_id, conf, priv_key, peers, log_level)
        self.log("Selfish node started.")

        # serves for selfish miner, who can validate balances of honest chain, too
        self.honest_bm = BalanceModel(self, peers)


    def mining_thread(self):

        self.log('Mining thread of selfish node started')
        self._wait_on_download_of_blockchain()

        fork_mark = None
        while True:

            self._preupdate_mined_txns()

            # start mining
            mined_block = self.blockchain.mine_next_block(self.pub_key, self.txns_to_mine, self.stop_mining_event, broadcast_whdrs=False)
            if self.stop_mining_event.is_set(): return

            if mined_block is not None:
                # we mined a new block
                fork_mark = self.blockchain.tip_block if not fork_mark else fork_mark
                self.blockchain.add_block(mined_block)
                self.blockchain.tip_block = mined_block
                self._update_txns_to_mine(mined_block)
                self.bm.update_balances(mined_block)
            else:
                # handle received new block
                rcv_block = self.q_strong.get()
                rcv_block.print_block_info()
                if not self._validate_recv_block(rcv_block):
                    continue

                state = self._add_or_ignore_block(rcv_block, fork_mark)
                if SMState.PUBLISH == state:
                    fork_mark = self.blockchain.tip_block

                elif SMState.WITHOLD == state:
                    pass

                elif SMState.GIVE_UP == state:
                    # we lost and we need to fork to a valid chain
                    self.blockchain.whdrs_cache = {}
                    self._update_txns_to_mine(rcv_block)
                    fork_mark = self.blockchain.tip_block

                else:
                    self.log("[ERROR]: Unknown state {}", str(state))

            #  print blockchain and balances
            self.blockchain.print_chain()
            self.bm.print_balances(LogLevel.DEBUG)


    def _add_or_ignore_block(self, rcv_block, fork_mark):

        self.blockchain.add_block(rcv_block)

        if rcv_block.header.prev_hash != self.blockchain.tip_block.header.hash:
            self.log("Adding block to another chain", True)


            # if honest chain is almost "catching up" with our selfish chain, then broadcast our selfish branch
            if self.blockchain.chainPoW(rcv_block)  > self.blockchain.chainPoW() + self.blockchain.current_whdrs_PoW() \
                        - SelfishNode.RATIO_TO_OVERRIDE * (Header.MAX_TARGET * rcv_block.header.target) \
                        and self.blockchain.chainPoW(rcv_block) < self.blockchain.chainPoW() + self.blockchain.current_whdrs_PoW():

                self.log(80 * 'X')
                self.log("[XXX] REVEALING HIDDEN CHAIN [XXX]")
                self.log(80 * 'X')

                blks_to_reveal = []
                cur_blk = self.blockchain.tip_block

                while cur_blk.header.hash != fork_mark.header.hash:
                    blks_to_reveal.insert(0, cur_blk)
                    cur_blk = self.blockchain.all_blocks[cur_blk.header.prev_hash]

                for b in blks_to_reveal:
                    self.log("Broadcasting block[{}] with hash = {}".format(b.length, b.header.hash), True)
                    self.broadcast(MsgType.STRONG_BLOCK_MINED, b)

                self.honest_bm.rebuild_balances_after_fork()

                return SMState.PUBLISH

            elif self.blockchain.chainPoW(rcv_block) < self.blockchain.chainPoW() + self.blockchain.current_whdrs_PoW():
                self.log("[XXX] We continue in witholding [XXX]")
                self.honest_bm.update_balances(rcv_block)
                return SMState.WITHOLD
            else:
                # we give up and have to switch to a stronger chain
                self.log("[###] Selfish miner gave up [###]")
                self.blockchain.tip_block = rcv_block
                self.bm.rebuild_balances_after_fork()
                self.honest_bm.update_balances(rcv_block)
                return SMState.GIVE_UP

        else:
            # we give at the beggining
            self.log("Updating my own chain", True)
            self.blockchain.tip_block = rcv_block
            self.bm.update_balances(rcv_block)
            self.honest_bm.update_balances(rcv_block)
            return SMState.GIVE_UP