# StrongChain

## Description
This proof-of-concept implementation contains full node that runs mining
process and at the same time provide an interactive client interface to the user.
Particular nodes can be run anytime, as blockchain is synchronized on start up.
The implementation uses account/balance model (not UTXO).

## Running Nodes

### Running a Known node
In the first shell, let log messages to be displayed on the fly:

$ `tail -f -n0 ./logs/node-1.log`

In the second shell, run a node, and its client interface, respectively:

$ `python3 ./BaseNode1.py [--verbose] [--selfish]`

### Running Other Known Nodes
Our implementation support 3 known nodes - called base nodes.
To run them, use the previous commands with index of node changed to `2` and `3`.


### Running an Unknown Node
In one shell:

$ `tail -f -n0 ./logs/node-1000.log`

In the next shell:

$ `python3 ./UnknownNode4.py`


## Interacting with the client

Display help and all available commands:

`> help`

`[chain]`:                              displays current blockchain

`[txns]`:                               displays all transactions made by this client

`[stats]`:                              displays statistics about miners

`[balance[s]]`:                         get my balance | all balances

`[send RECEIVER, AMOUNT [, COMMENT]]`:  sends crypto-tokens to RECEIVER, including optional comment

`[block ID]`:                           displays info about block with length = ID

`[whdrs]`:                              displays current cache of weak headers

`[exit | quit]`:                        ends operation of this node

`[verbose [on | off]]`                  enables verbose at log file.

`[help | h]`:                           shows this help



