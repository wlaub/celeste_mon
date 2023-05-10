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

        self.parse()

    def encode(self):
        stamp_raw = struct.pack('f', self.stamp)
        return stamp_raw + self.id_raw + self.sig_raw + self.size_raw + self.data

    def parse(self):
        self.is_state = False
        self.nocontrol = False
        self.dead = False
        self.statuses = []

        #find status string
        offset = self.data.find(b'Pos')
        if offset == -1:
            self.status_string = ''
        else:
            strlen = self.data[offset-2]
            if strlen == 0:
                strlen = self.data[offset-1]
            raw = self.data[offset:offset+strlen].decode('ascii')
            self.status_string = raw

        if len(self.status_string) == 0:
            pass
        else:
            self.decode_info_string()

    def decode_status_line(self, line):
        liftboost_re = '.*?\((.*)\): (.*?), (.*)'

        if line.startswith('Stamina'):
            parts = line.split()
            stam = parts[1]
            self.stamina = float(stam)
            self.state = parts[2:]
        elif line.startswith('LiftBoost'):
            m = re.match(liftboost_re, line)
            self.liftboost = m .groups()
        elif line.startswith('NoControl'):
            self.nocontrol = True
        else:
            parts =  line.split()
            for part in parts:
                if '(' in part:
                    part = part.split('(')[0]
                if part == 'Dead':
                    self.dead=True
                self.statuses.append(part)

    def decode_info_string(self):
        lines = [x.strip() for x in self.status_string.split('\n')]

        #position
        _, x, y = lines[0].split()
        self.pos = (float(x[:-1]), -float(y))

        #speed
        _, x, y = lines[1].split()       
        self.speed = (float(x[:-1]), -float(y))

        #velocity
        _, x, y = lines[2].split()
        self.speed = (float(x[:-1]), -float(y))

        for line in lines[3:-1]:
            self.decode_status_line(line)

        room, _, time = lines[-1].split()
        self.room = room[1:-1]
        _, frame = time.split('(')
        frame = frame.split(')')[0]
        self.frame = int(frame)

        self.is_state=True

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
            raise
            print(e)
            pass
        if len(msgs) > 30000:
            break

#my magic state machine
sequences = []
sequence = []

def end_sequence(seq, seqs):
    if len(seq) > 0:
        seqs.append(seq)
        return []
    else:
        return seq

for msg in msgs:
    if not msg.is_state:
        sequence = end_sequence(sequence, sequences)
    else:
        if msg.nocontrol or msg.dead:
            if len(sequence) > 0:
                sequence.append(msg)
            sequence = end_sequence(sequence, sequences)
        else:
            sequence.append(msg)

fig, ax = plt.subplots()

xdeaths = []
ydeaths = []
xspawns = []
yspawns = []
for seq in sequences:
    xvals = []
    yvals = []
    for msg in seq:
        xvals.append(msg.pos[0])
        yvals.append(msg.pos[1])

    if seq[-1].dead:
        xdeaths.append(seq[-1].pos[0])
        ydeaths.append(seq[-1].pos[1])

    xspawns.append(seq[0].pos[0])
    yspawns.append(seq[0].pos[1])

    zorder = 0
    color = 'k'
    alpha = 0.25
    if seq[-1].nocontrol:
        color='#00ff00'
        zorder = 10
        alpha = 1
    elif seq[-1].dead:
        pass
    else:
        color = 'b'
        zorder = 10
        alpha = 1

    ax.scatter(xvals, yvals, s=1, c=color, zorder=zorder, alpha = alpha)
    
ax.scatter(xdeaths, ydeaths, s=8, marker='x', c='r')
ax.scatter(xspawns, yspawns, s=8, c='b')
ax.set_aspect('equal')
plt.show()

print(len(sequences))
print(len(msgs))

