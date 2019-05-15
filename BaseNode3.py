#!/usr/bin/python3

from config import BASE_NODES
from strongchain import NodeController, ArgParser

THIS_NODE_IDX = 2

MY_SK = '982398a6548a7a30b735c531bf0be344db9f1c9be1a1f501'

if __name__ == "__main__":

    args = ArgParser.parse_args()
    controller = NodeController(THIS_NODE_IDX, BASE_NODES[THIS_NODE_IDX], BASE_NODES, MY_SK, args)
    controller.start_threads()
