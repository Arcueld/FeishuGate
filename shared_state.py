import threading
import time


index = 2
lock = threading.Lock()


def get_index():
    with lock:
        return index

def increment_index():
    global index
    with lock:
        index += 1
        
def reset_index():
    global index
    with lock:
        index = 2
