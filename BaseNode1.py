#!/usr/bin/python3

from config import BASE_NODES
from strongchain import NodeController, ArgParser

THIS_NODE_IDX = 0

MY_SK = '5a121ad3216b4a529bc3856e8471d21a6f400af81d3b4ade'

if __name__ == "__main__":

    args = ArgParser.parse_args()
    controller = NodeController(THIS_NODE_IDX, BASE_NODES[THIS_NODE_IDX], BASE_NODES, MY_SK, args)
    controller.start_threads()
