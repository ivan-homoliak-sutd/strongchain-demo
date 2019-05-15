import hashlib


class MerkleTree:
    def __init__(self, leaves_list):
        self.nodes = []
        self.tree = []
        self.proof_path = []
        for leave in leaves_list:
            self.nodes.append(single_hash(leave))
        self.tree.append(self.nodes)
        self.build(self.nodes)
        self.root = self.get_root()

    @classmethod
    def compute_root(cls, leaves):
        tree = cls(leaves)
        return tree.root

    def add(self, new_leave):
        # Add entries to tree
        self.nodes.append(single_hash(new_leave))
        self.tree = []
        self.tree.append(self.nodes)
        self.build(self.nodes)
        self.root = self.get_root()

    def build(self, start_list):
        # Build tree computing new root
        if 0 == len(start_list):
            return '0' * 64

        end_list = []
        if len(start_list) > 1:
            if len(start_list) % 2 == 0:
                for i in range(0, len(start_list), 2):
                    end_list.append(double_hash(start_list[i], start_list[i + 1]))
            else:
                for i in range(0, len(start_list) - 1, 2):
                    end_list.append(double_hash(start_list[i], start_list[i + 1]))
                end_list.append(start_list[-1])
            self.tree.append(end_list)
            return self.build(end_list)

        else:
            if len(self.tree) == 0:
                end_list.append(start_list[0])
                self.tree.append(end_list)
                return start_list[0]

    def get_proof(self, entry):
        self.proof_path = []
        if int(entry) > len(self.nodes) - 1:
            return []

        else:
            next_entry = entry
            for i in range(0, len(self.tree) - 1):
                if len(self.tree[i]) != 1:
                    if int(next_entry) % 2 == 0:
                        if int(next_entry) != len(self.tree[i]) - 1:
                            self.proof_path.append([self.tree[i][int(next_entry) + 1], 'r'])
                    else:
                        self.proof_path.append([self.tree[i][int(next_entry) - 1], 'l'])
                next_entry = get_next_entry(next_entry)
            return self.proof_path

    def get_root(self):

        # Return the current root
        if 0 == len(self.tree[-1]):
            return '0' * 64

        return str(self.tree[-1][0])


def single_hash(value):

    if not isinstance(value, str):
        value = str(value)

    return hashlib.sha256(value.encode()).hexdigest()


def double_hash(node1, node2):
    return hashlib.sha256((node1 + node2).encode()).hexdigest()


def get_next_entry(value):
    if value <= 1:
        return 0
    else:
        if value % 2 == 0:
            return int(value / 2)
        else:
            return int((value - 1) / 2)


def verify_proof(entry, proof, root):
    test_val = single_hash(entry)
    for i in range(0, len(proof)):
        if proof[i][1] == 'l':
            test_val = double_hash(proof[i][0], test_val)
        else:
            test_val = double_hash(test_val, proof[i][0])
    return test_val == root
