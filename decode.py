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

states = [
'StNormal',
'StClimb',
'StDash',
'StSwim',
'StBoost',
'StRedDash',
'StHitSquash',
'StLaunch',
'StPickup',
'StDreamDash',
'StSummitLaunch',
'StDummy',
'StIntroWalk',
'StIntroJump',
'StIntroRespawn',
'StIntroWakeUp',
'StBirdDashTutorial',
'StFrozen',
'StReflectionFall',
'StStarFly',
'StTempleFall',
'StCassetteFly',
'StAttract',
]

class Bounds():
    def __init__(self):
        self.bounds = None

    def update(self, xpos, ypos):
        if self.bounds is None:
            self.bounds = [
                xpos, xpos, 
                ypos, ypos
                ]
        else:
            self.bounds[0] = min(self.bounds[0], xpos)
            self.bounds[1] = max(self.bounds[1], xpos)
            self.bounds[2] = min(self.bounds[2], ypos)
            self.bounds[3] = max(self.bounds[3], ypos)

    def expand(self, other):
        if self.bounds is None:
            self.bounds = list(other.bounds)
        else:
            self.bounds[0] = min(self.bounds[0], other.bounds[0])
            self.bounds[1] = max(self.bounds[1], other.bounds[1])
            self.bounds[2] = min(self.bounds[2], other.bounds[2])
            self.bounds[3] = max(self.bounds[3], other.bounds[3])

    def plot(self, ax, line='k', fill='none', zorder=-10):
        bounds = self.bounds        
        rect = patches.Rectangle(
                    (bounds[0], bounds[2]), bounds[1]-bounds[0], bounds[3]-bounds[2],
                    linewidth = 1, edgecolor = line, facecolor=fill, zorder=zorder
                    )
        ax.add_patch(rect)

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
        self.retained = False
        self.retain_value = 0
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
            self.state = []
            self.wall = None
            for state in parts[2:]:
                if 'St' in state:
                    if state == 'StIntroRespawn':
                        self.dead = True
                    self.state.append(state)
                elif 'Wall' in state:
                    self.wall = state
                else:
                    print(f'Unhandled state: {state}')
        elif line.startswith('LiftBoost'):
            m = re.match(liftboost_re, line)
            self.liftboost = m .groups()
        elif line.startswith('NoControl'):
            self.nocontrol = True
        elif line.startswith('Retained'):
            self.retained = True
            self.retain_value = float(line.split(' ')[-1])
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
        self.nocontrol = False

        self.spacejams = []

    def valid(self):
        return len(self.msgs) != 0

    def add_msg(self, msg):
        if self.done:
            print('Cant add msg: run complete.')
            return self.done

        if msg.nocontrol:
            self.nocontrol = True
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

        sizes = []
        colors = []
        markers = []

        self.state_bounds = defaultdict(list)

        last_msg = None
        for msg in self.msgs:
            xvals.append(msg.pos[0])
            yvals.append(msg.pos[1])

            marker = '.'
            size = 1
            color = 'k'
            if not self.dead:
                color = '#ff00ff'

            if msg.dead:
                marker = 'x'
                size = 10
                color = 'r'
            elif 'StDash' in msg.state:
                if msg.speed[1] == 0:
                    marker = '_'  
                elif msg.speed[0] == 0:
                    marker = '|'
                else:
                    marker = 'x'
                size = 8
            elif 'StClimb' in msg.state:
                marker = 'd'
                if msg.wall is None:
                    pass
                elif 'L' in msg.wall:
                    marker = 4 #caretleft
                else:
                    marker = 5 #caretright
                size = 8
            elif 'StRedDash' in msg.state:
                marker = 'o'
                size = 16
                color = 'r'
            elif 'StDreamDash' in msg.state:
                color = 'w'
                marker = 'x'
                size = 8
            elif 'StSwim' in msg.state:
                color = 'b'
                size = 2
            else:
                marker = '.'

            sizes.append(size)
            colors.append(color)
            markers.append(marker)
            
            if last_msg is not None:
                for state in states:
                    if state in msg.state:
                        if not state in last_msg.state or len(self.state_bounds[state]) == 0:
                            self.state_bounds[state].append(Bounds())
                        self.state_bounds[state][-1].update(*msg.pos)

            last_msg = msg

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

        def mscatter(x,y,ax=None, m=None, **kw):
            import matplotlib.markers as mmarkers
            if not ax: ax=plt.gca()
            sc = ax.scatter(x,y,**kw)
            if (m is not None) and (len(m)==len(x)):
                paths = []
                for marker in m:
                    if isinstance(marker, mmarkers.MarkerStyle):
                        marker_obj = marker
                    else:
                        marker_obj = mmarkers.MarkerStyle(marker)
                    path = marker_obj.get_path().transformed(
                                marker_obj.get_transform())
                    paths.append(path)
                sc.set_paths(paths)
            return sc
        mscatter(xvals, yvals, s=sizes, c=colors, m=markers, zorder=zorder, alpha=alpha)
#        sc = ax.scatter(xvals, yvals, s=sizes, c=colors, zorder=zorder, alpha = alpha)

        ax.scatter(xdeaths, ydeaths, s=8, marker='x', c='r')
        ax.scatter(xspawns, yspawns, s=8, c='b')

        for bounds in self.state_bounds['StDreamDash']:
            bounds.plot(ax, 'w', 'k', zorder=-10)


class Room():
    def __init__(self):
        self.name = None
        self.runs = []
        self.trun = Run()
        self.done = False

        self.bounds = Bounds()
        self.start_idx = None
        self.end_idx = None

    def key(self):
        return (self.name, self.start_idx, self.end_idx)

    def valid(self):
        return len(self.runs) != 0

    def index_data(self):
        return {
            'start': self.start_idx,
            'end': self.end_idx,
            'runs': len(self.runs),
            }

    def update_bounds(self, msg):
        self.bounds.update(*msg.pos)

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

#    boop = set()
#    for msg in msgs:
#        boop.update(msg.state)
#        if not msg.is_state:
#            print(msg.data)
#    print(boop)

    return msgs

def make_index(rooms):
    index = defaultdict(list)
    for room in rooms:
        index[room.name].append(room.index_data())
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
    for entry in index[room_name]:
        start = entry['start']
        end = entry['end']
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
        bounds = Bounds()
        for room in self.get_room(room_name):
            room.plot(ax)
            runs += len(room.runs)
            bounds.expand(room.bounds)

        title = f'{room_name}: {runs} runs '

        bounds.plot(ax, 'k', 'none')

        ax.text(bounds.bounds[0], bounds.bounds[2], title, fontsize=8)

    def print_rooms(self):
        lines = []
        for room, entries in self.index.items():
            runs = sum(x['runs'] for x in entries)
            line = f'{room}: {runs} runs'
            lines.append(line)

        print('\n'.join(lines))

    def configure_ax(self, ax):
        ax.set_aspect('equal')
        ax.xaxis.set_major_locator(ticker.MultipleLocator(base=8))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(base=8))
        ax.grid(True, which='major', axis='both')
        ax.set_axisbelow(True)


if __name__ == '__main__':
    infile = sys.argv[1]
    rooms = RoomSet(infile)

    rooms.print_rooms()

    if len(sys.argv[2:]) == 0:
        exit()


    fig, ax = plt.subplots()
    for name in sys.argv[2:]:
        rooms.plot_room(ax, name)

    #for name in ['c-01','c-02', 'c-03', 'c-04', 'c-b1', 'c-06', 'c-07', 'e-02']:
    #    rooms.plot_room(ax, name)
    #rooms.plot_room(ax, 'C13berry')
    #rooms.plot_room(ax, 'C11')
    #rooms.plot_room(ax, 'C12')
    rooms.configure_ax(ax)
    plt.show()

