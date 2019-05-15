
from enum import Enum

class MsgType:
    STRONG_BLOCK_MINED = 1
    WEAK_HEADER_MINED  = 2
    NEW_PEER     = 3
    NEW_PEER_ACK  = 4
    TRANSACTION  = 5
    GET_BLOCK    = 6
    BLOCK        = 7

class LogLevel:
    ERROR = 1
    INFO  = 2
    DEBUG = 3
    NONE = 4


class SelfishMState(Enum):
    WITHOLD    = 1
    PUBLISH    = 2
    GIVE_UP    = 3

class BlockValidationStatus(Enum):
    NON_EXISTING_PRED   = -1
    EXISTING_BLOCK      = -2
    TXNS_INTEGRITY      = -3
    WHDRS_INTEGRITY     = -4
    TARGET_VALUE        = -5
    STRONG_TARGET_POW   = -6
    HDR_TIMESTAMP       = -7
    WHDR_TIMESTAMP      = -8
    WHDR_PREV_HASH      = -9
    WHDR_TARGET_POW     = -10
    WHDR_TARGET_VALUE   = -11
    OK                  = 0
    WHDR_OK             = 1

