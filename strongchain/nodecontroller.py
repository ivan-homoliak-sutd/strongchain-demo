
from .node import Node
from .client import Client
from .lib.enums import LogLevel
from .selfishnode import SelfishNode

import threading

class NodeController:
    'Bootstraps the node and the associated client.'

    def __init__(self, _id, this_node_conf, nodes, sk, args):

        self.all_nodes = nodes
        self.node_id = _id
        self.conf = this_node_conf

        if not args.selfish:
            self.node = Node(self.node_id + 1, self.conf, sk,
                peers = [p for p in self.all_nodes if p.vk != self.conf.vk],
                log_level = LogLevel.DEBUG if args.verbose else LogLevel.INFO
            )
        else:
            self.node = SelfishNode(self.node_id + 1, self.conf, sk,
                peers = [p for p in self.all_nodes if p.vk != self.conf.vk],
                log_level = LogLevel.DEBUG if args.verbose else LogLevel.INFO
            )
        self.client = Client(self.conf.vk, sk, self.node)
        self.child_threads = []


    def start_threads(self):

        self._start_backend()
        self._start_frontend()


    def _start_backend(self):

        # create and start mining nodes with all peers included
        mp_name = 'Node-{}: mining thread'.format(self.node_id + 1)
        mining_t = threading.Thread(
            target = self._mining_thread_wrapper,
            args=(mp_name,),
            name=mp_name
        )
        lp_name = 'Node-{}: listening thread'.format(self.node_id + 1)
        listen_t = threading.Thread(
            target = self._listening_thread_wrapper,
            args=(lp_name,),
            name=lp_name
        )
        mining_t.start()
        listen_t.start()
        self.child_threads.extend([mining_t, listen_t])


    def _start_frontend(self):
        'This is served by a parent thread'

        try:
            self.client.serve_loop()
        except KeyboardInterrupt:
            pass

        print("Killing child threads...")
        self.node.stop_listening_event.set()
        self.node.stop_mining_event.set()

        for t in self.child_threads:
            t.join()


    def _mining_thread_wrapper(self, t_name):
        self.node.mining_thread()
        print(" [INFO]: {} terminated.".format(t_name))



    def _listening_thread_wrapper(self, t_name):
        self.node.listening_thread()
        print(" [INFO]: {} terminated.".format(t_name))


