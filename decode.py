import time
import sys
import struct
import mmap
import enum
import re
import itertools
import json
import os
from collections import defaultdict

from matplotlib import pyplot as plt
from matplotlib import ticker, patches

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
        self.file_start_idx = fp.tell()

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

        self.file_end_idx = fp.tell()-1

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

        try:
            #TODO: handle truncated lines
            room, _, time = lines[-1].split()
            self.room = room[1:-1]
            _, frame = time.split('(')
            frame = frame.split(')')[0]
            self.frame = int(frame)
        except:
            self.room = lines[-1].split(']')[0][1:]
            self.frame = -1
            print(lines[-1])

        self.is_state=True

    def __str__(self):
        return f'{self.pos}'

    def __repr__(self):
        return str(self)


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
            color='#ff00ff'
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
        self.start_idx = None
        self.end_idx = None

    def key(self):
        return (self.name, self.start_idx, self.end_idx)

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
            self.bounds[0] = min(self.bounds[0], msg.pos[0])
            self.bounds[1] = max(self.bounds[1], msg.pos[0])
            self.bounds[2] = min(self.bounds[2], msg.pos[1])
            self.bounds[3] = max(self.bounds[3], msg.pos[1])


    def update_index(self, msg):
        if self.start_idx is None:
            self.start_idx = msg.file_start_idx

        self.end_idx = msg.file_end_idx

    def add_msg(self, msg):
        if self.done:
            print('Cant add msg: room complete.')
            return self.done
        
        if not msg.is_state:
            return self.done


        if self.name is None:
            self.name = msg.room

        self.update_bounds(msg)
        self.update_index(msg)

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

    def __repr__(self):
        return f'{self.name}: {len(self.runs)} runs\nBounds: {self.bounds}'

def read_file(filename, start = 0, stop=None, limit = None):
    msgs = []

    with open(filename, 'rb') as fp:
        fp.seek(start)
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
            if stop is not None and fp.tell() >= stop:
                break
            if limit is not None and len(msgs) > limit:
                break

    return msgs

def make_index(rooms):
    index = defaultdict(list)
    for room in rooms:
        index[room.name].append([room.start_idx, room.end_idx])
    return index

def write_index(filename, index):
    with open(filename, 'w') as fp:
        json.dump(index, fp)

def read_index(filename):
    with open(filename, 'r') as fp:
        data = json.load(fp)
    return data

def load_room_from_index(filename, index, room_name):
    result = []
    for start, end in index[room_name]:
        msgs = read_file(filename, start, end)
        rooms = extract_rooms(msgs)
        if len(rooms) != 1:
            raise RuntimeError(f'Got {len(rooms)} rooms from {room_name}, {start}, {end}')
        result.extend(rooms)
    return result

def extract_rooms(msgs):

    troom = Room()
    rooms = []
    for msg in msgs:
        troom.add_msg(msg)
        if troom.done and troom.valid():
            print(troom)
            rooms.append(troom)
            troom = Room()
    if troom.valid() and  not troom in rooms:
        rooms.append(troom)

    return rooms



class RoomSet():
    def __init__(self, infile):
        self.infile = infile
        idxfile= self.idxfile = os.path.splitext(infile)[0]+'_index.json'
        self.room_map = defaultdict(list)
        if not os.path.exists(idxfile):
            self.generate_index()
        else:
            self.index = read_index(self.idxfile)

    def generate_index(self):
        print(f'Generating index...')
        msgs = read_file(self.infile)
        rooms = extract_rooms(msgs)
        index = self.index = make_index(rooms)
        write_index(self.idxfile, self.index)
        for room in rooms:
            self.room_map[room].append(room)

    def get_room(self, room_name):
        if not room_name in self.room_map.keys():
            rooms = load_room_from_index(self.infile, self.index, room_name)
            self.room_map[room_name] = rooms
        return self.room_map[room_name]

    def plot_room(self, ax, room_name):
        runs = 0
        bounds = None
        for room in self.get_room(room_name):
            room.plot(ax)
            runs += len(room.runs)
            if bounds is None:
                bounds = room.bounds
            else:
                bounds[0] = min(bounds[0], room.bounds[0])
                bounds[1] = max(bounds[1], room.bounds[1])
                bounds[2] = min(bounds[2], room.bounds[2])
                bounds[3] = max(bounds[3], room.bounds[3])

        title = f'{room_name}: {runs} runs '
        print(bounds)

        rect = patches.Rectangle(
                    (bounds[0], bounds[2]), bounds[1]-bounds[0], bounds[3]-bounds[2],
                    linewidth = 1, edgecolor = 'k', facecolor='none',
                    )
        ax.add_patch(rect)

    def configure_ax(self, ax):
        ax.set_aspect('equal')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(base=8))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(base=8))
        ax.grid(True, which='major', axis='both')
        ax.set_axisbelow(True)


infile = sys.argv[1]
rooms = RoomSet(infile)

fig, ax = plt.subplots()
rooms.plot_room(ax, 'C13berry')
rooms.plot_room(ax, 'C11')
rooms.plot_room(ax, 'C12')
rooms.configure_ax(ax)
plt.show()

