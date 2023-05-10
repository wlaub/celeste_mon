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
        if len(msgs) > 35000:
            break


class Run():
    def __init__(self):
        self.msgs = []
        self.dead = False
        self.done = False

    def valid(self):
        return len(self.msgs) != 0

    def add_msg(self, msg):
        if self.done:
            print('Cant add msg: run complete.')
            return self.done

        if msg.nocontrol:
            self.done = True
        if msg.dead:
            self.dead = True
            self.done = True

        if not self.done or self.valid():
            self.msgs.append(msg)

        return self.done

    def plot(self, ax):
        xdeaths = []
        ydeaths = []
        xspawns = []
        yspawns = []
        xvals = []
        yvals = []
        for msg in self.msgs:
            xvals.append(msg.pos[0])
            yvals.append(msg.pos[1])

        if self.dead:
            xdeaths.append(self.msgs[-1].pos[0])
            ydeaths.append(self.msgs[-1].pos[1])

        xspawns.append(self.msgs[0].pos[0])
        yspawns.append(self.msgs[0].pos[1])

        zorder = 0
        color = 'k'
        alpha = 0.25
        if not self.dead:
            color='#00ff00'
            zorder = 10
            alpha = 1

        ax.scatter(xvals, yvals, s=1, c=color, zorder=zorder, alpha = alpha)
        ax.scatter(xdeaths, ydeaths, s=8, marker='x', c='r')
        ax.scatter(xspawns, yspawns, s=8, c='b')
   

class Room():
    def __init__(self):
        self.name = None
        self.runs = []
        self.trun = Run()
        self.done = False

        self.bounds = None

    def valid(self):
        return len(self.runs) != 0

    def update_bounds(self, msg):
        if self.bounds is None:
            self.bounds = [
                msg.pos[0], #xmin
                msg.pos[0], #xmax
                msg.pos[1], #ymin
                msg.pos[1], #ymax
                ]
        else:
            if msg.pos[0] < self.bounds[0]:
                self.bounds[0] = msg.pos[0]
            if msg.pos[0] > self.bounds[1]:
                self.bounds[1] = msg.pos[0]
            if msg.pos[1] < self.bounds[0]:
                self.bounds[0] = msg.pos[1]
            if msg.pos[1] > self.bounds[1]:
                self.bounds[1] = msg.pos[1]

    def add_msg(self, msg):
        if self.done:
            print('Cant add msg: room complete.')
            return self.done
        
        if not msg.is_state:
            return self.done


        if self.name is None:
            self.name = msg.room

        self.update_bounds(msg)

        if msg.room != self.name:
            self.trun.done = True
            if self.trun.valid():
                self.runs.append(self.trun)
            self.done = True
            return self.done

        self.trun.add_msg(msg)
        if self.trun.done:
            if self.trun.valid():
                self.runs.append(self.trun)
            self.trun = Run()

        return False

    def plot(self, ax):
        for run in self.runs:
            run.plot(ax)
        #TODO: draw box

        ax.set_aspect('equal')

    def __repr__(self):
        return f'{self.name}: {len(self.runs)} runs\nBounds: {self.bounds}'

troom = Room()
rooms = []
for msg in msgs:
    troom.add_msg(msg)
    if troom.done and troom.valid():
        print(troom)
        rooms.append(troom)
        troom = Room()
if not troom in rooms:
    rooms.append(troom)

fig, ax = plt.subplots()

rooms = sorted(rooms, key=lambda x:len(x.runs), reverse=True)
rooms[0].plot(ax)

#for room in rooms:
#    room.plot(ax)
plt.show()

print(len(rooms))

