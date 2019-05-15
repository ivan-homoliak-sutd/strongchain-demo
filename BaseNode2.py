#!/usr/bin/python3

from config import BASE_NODES
from strongchain import NodeController, ArgParser

THIS_NODE_IDX = 1

MY_SK = 'd1c600fc112f4f10af250c0eea653182ecbcb3711abef5e0'

if __name__ == "__main__":

    args = ArgParser.parse_args()
    controller = NodeController(THIS_NODE_IDX, BASE_NODES[THIS_NODE_IDX], BASE_NODES, MY_SK, args)
    controller.start_threads()
