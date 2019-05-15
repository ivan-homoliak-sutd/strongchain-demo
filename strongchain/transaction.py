import json
import ecdsa
import hashlib

class Transaction:

    def __init__(self, sender_pk, receiver_pk, amount, signature, comment=''):
        self.sender = sender_pk
        self.receiver = receiver_pk
        self.amount = amount
        self.comment = comment
        self.signature = signature


    def to_json(self):
        return {
            'sender': self.sender,
            'receiver': self.receiver,
            'amount': self.amount,
            'comment': self.comment,
            'signature': self.signature
        }


    def to_json_str(self):
        return json.dumps(self.to_json(), indent = 4)


    def __str__(self):
        return self.to_json_str()

    @property
    def hash(self):
        to_hash = {'sender': self.sender,
                     'receiver': self.receiver,
                     'amount': self.amount,
                     'comment': self.comment,
        }
        return hashlib.sha256(str(to_hash).encode()).hexdigest()


    def validate_sig(self):
        local_msg = self.hash
        msg_byte = str(local_msg).encode('utf-8')

        try:
            vk = ecdsa.VerifyingKey.from_string(bytes.fromhex(self.sender), curve = ecdsa.NIST192p)
            if vk.verify(bytes.fromhex(self.signature), msg_byte):
                return True
        except ecdsa.keys.BadSignatureError:
            pass

        return False


    def __eq__(self, other):
        return self.amount == int(other.amount) and \
               self.sender == other.sender and \
               self.receiver == other.receiver and \
               self.signature == other.signature and \
               self.comment == other.comment


    @classmethod
    def from_json(cls, j):
        return cls(j.get("sender"), j.get("receiver"), float(j.get("amount")), j.get("signature"), j.get("comment"))


    @classmethod
    def from_json_str(cls, json_string):
        j = json.loads(json_string)
        return Transaction.from_json(j)