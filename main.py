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
        fp.seek(0)
        self.id_raw = fp.read(1)
        id_ = ord(self.id_raw)
        self.stamp = time.time()
        self.id = MessageId(id_)
        self.sig_raw = fp.read(4)
        self.signature = struct.unpack('I', self.sig_raw)[0]
        self.size_raw = fp.read(4)
        self.size = struct.unpack('I', self.size_raw)[0]
        self.data = fp.read(self.size)

    def encode(self):
        stamp_raw = struct.pack('d', self.stamp)
        return stamp_raw + self.id_raw + self.sig_raw + self.size_raw + self.data

    def decode_info_string(self):

        offset = self.data.find(b'Pos')
        strlen = self.data[offset-2]
        if strlen == 0:
            strlen = self.data[offset-1]
        raw = self.data[offset:offset+strlen].decode('ascii')
        self.status_string = raw
        

        lines = [x.strip() for x in raw.split('\n')]
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

        _, stam, state = lines[3].split()
        self.stamina = float(stam)
        self.stamina_state = state

        self.statuses = lines[4:-1]

        room, _, time = lines[-1].split()
        self.room = room[1:-1]
        _, frame = time.split('(')
        self.frame = int(frame[:-1])

    def __str__(self):
        return f'{self.pos}'

    def __repr__(self):
        return str(self)

#outfile = 'test.bin'
outfile = time.strftime('%Y-%m-%d-%H%M%S.dat')

try:
    buffersize = 0x100000
    with mmap.mmap(-1, buffersize, 'CelesteTAS') as fp:
        last_msg = Message(fp)
        last_unique = None
        msg = None
        while True:
            time.sleep(.001)
            try:
                msg = Message(fp)
            except ValueError:
                print(f'Error: {msg}')
                continue

            if msg.data != last_msg.data:
                if last_unique is not None:
                    print(f'{(msg.stamp - last_unique.stamp)*60:.2f}')
                with open(outfile, 'ab') as fpo:
                    fpo.write(msg.encode())
                last_unique = msg


            last_msg = msg
except KeyboardInterrupt:
    pass



