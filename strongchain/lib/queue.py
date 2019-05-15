
import threading

class QueueEmpty(Exception):
    'Empty queue.'
    pass

class Queue:

    def __init__(self):
        self._lock = threading.Lock()
        self._q = []

    def get(self):
        with self._lock:
            if 0 == len(self._q):
                raise QueueEmpty

            return self._q.pop()

    def put(self, item):
        with self._lock:
            self._q.insert(0, item)

    def empty(self):
        with self._lock:
            return False if len(self._q) else True


