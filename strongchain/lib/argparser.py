
import argparse

ArgParser = argparse.ArgumentParser(add_help = True, description = "Management Tool of StrongChain")

group = ArgParser.add_argument_group(title = "Node Options")
group.add_argument('--verbose', action = "store_true", default = False, help = "Display verbose messages in node's log.")
group.add_argument('--selfish', action = "store_true", default = False, help = "Act as a selfish miner.")