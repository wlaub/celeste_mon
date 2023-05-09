import time
import sys
import struct
import mmap
import enum
import re
import itertools
from matplotlib import pyplot as plt

class MessageId(enum.Enum):
    default = 0x00
    version_info = 0x01
    get_data = 0x08
    establish_connection = 0x0d
    wait = 0x0e
    reset = 0x0f
    send_state = 0x10
    send_path = 0x20
    send_hotkey_pressed = 0x21
    convert_to_lib_tas = 0x24
    send_current_bindings = 0x30
    return_data = 0x31
    update_lines = 0x32



class Message():
    def __init__(self, fp):
        self.stamp_raw = fp.read(8)
        if len(self.stamp_raw) == 0:
            raise RuntimeError('done')

        self.stamp = struct.unpack('d', self.stamp_raw)[0]
        self.id_raw = fp.read(1)
        id_ = ord(self.id_raw)
        self.id = MessageId(id_)
        self.sig_raw = fp.read(4)
        self.signature = struct.unpack('I', self.sig_raw)[0]
        self.size_raw = fp.read(4)
        self.size = struct.unpack('I', self.size_raw)[0]
        self.data = fp.read(self.size)

        self.decode_info_string()

    def encode(self):
        stamp_raw = struct.pack('f', self.stamp)
        return stamp_raw + self.id_raw + self.sig_raw + self.size_raw + self.data

    def decode_info_string(self):

        offset = self.data.find(b'Pos')
        strlen = self.data[offset-2]
        if strlen == 0:
            strlen = self.data[offset-1]
        raw = self.data[offset:offset+strlen].decode('ascii')
        self.status_string = raw
        
        lines = [x.strip() for x in raw.split('\n')]
        print(self.stamp)
        print(lines)
        try:
            _, x, y = lines[0].split()
            self.pos = (float(x[:-1]), -float(y))
        except:
            print(self.data)
            print(raw)
            print(self.status_string)
            print(f'--> {lines[0]}')
            raise

        _, x, y = lines[1].split()       
        self.speed = (float(x[:-1]), -float(y))

        _, x, y = lines[2].split()
        self.speed = (float(x[:-1]), -float(y))

        parts = lines[3].split()
        stam = parts[1]
        self.stamina = float(stam)
        self.state = parts[2:]

        self.statuses = lines[4:-1]

        room, _, time = lines[-1].split()
        self.room = room[1:-1]
        _, frame = time.split('(')
        self.frame = int(frame[:-1])

    def __str__(self):
        return f'{self.pos}'

    def __repr__(self):
        return str(self)

msgs = []

with open(sys.argv[1], 'rb') as fp:
    while True:
        try:
            msg = Message(fp)
            msgs.append(msg)
        except RuntimeError:
            break
        except Exception as e:
            print(e)
            pass


print(len(msgs))

