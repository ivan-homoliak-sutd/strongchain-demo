#!/usr/bin/python3

from ecdsa import SigningKey

from config import BASE_NODES
from strongchain import NodeController, ArgParser, NodeConf

sk = SigningKey.generate()

MY_SK = sk.to_string().hex()
MY_VK = sk.get_verifying_key().to_string().hex()
MY_CONF = NodeConf(30100, 'localhost', MY_VK)

THIS_NODE_IDX = 999

if __name__ == "__main__":

    args = ArgParser.parse_args()
    controller = NodeController(THIS_NODE_IDX, MY_CONF, BASE_NODES, MY_SK, args)
    controller.start_threads()
