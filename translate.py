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

import clr
import System

from System.Runtime.Serialization.Formatters.Binary import BinaryFormatter
from System.Runtime.Serialization import SerializationException
from System.IO import MemoryStream

serializer = BinaryFormatter()

from model import MessageId, state_to_idx, Status
from party import GameState


class IgnoreMessage(Exception):
    pass

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

#        if self.id in {MessageId.send_current_bindings}:
#            raise IgnoreMessage


        self.sig_raw = fp.read(4)
        self.signature = struct.unpack('I', self.sig_raw)[0]
        self.size_raw = fp.read(4)
        self.size = struct.unpack('I', self.size_raw)[0]
        self.raw = fp.read(self.size)

        self.file_end_idx = fp.tell()-1

        self.decode()

        try:
            self.decode_info_string()
        except:
            print(self.id)
            raise

    def decode(self):
        reader = MemoryStream(self.raw)
        data = serializer.Deserialize(reader)
        self.data = list(data)
        if len(self.data) != 9:
            print(self.id)
            print(len(self.data))
            raise IgnoreMessage

        reader.Close()

        (self.current_line, self.current_line_suffix, self.current_frame_in_tas,
        self.total_frames, self.savestate_line, self.tas_states,
        self.game_info, self.level_name, self.chapter_time
        ) = self.data


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
            g = m.groups()
            self.liftboost = [int(g[0]), float(g[1]), float(g[2])]
        elif line.startswith('Retained'):
            self.retained = True
            self.retain_frame = int(line.split('(')[1].split(')')[0])
            self.retain_value = float(line.split(' ')[-1])
        elif line.startswith('Retained'):
            self.statuses
        else:
            parts =  line.split()
            for part in parts:
                self.statuses.append(Status.parse(part))

    def decode_info_string(self):
        self.statuses = []
        self.states = []
        self.wall = None
        self.stamina = 0
        self.retained = False
        self.retain_value = None
        self.liftboost = None
        self.pos = [0,0]
        self.speed=[0,0]
        self.vel=[0,0]
        self.frame = 0


        if not self.game_info.startswith('Pos'):
            self.room = self.game_info
            return

        lines = [x.strip() for x in self.game_info.split('\n')]

        #position
        _, x, y = lines[0].split()
        self.pos = (float(x[:-1]), -float(y))

        #speed
        _, x, y = lines[1].split()       
        self.speed = (float(x[:-1]), -float(y))

        #velocity
        _, x, y = lines[2].split()
        self.vel = (float(x[:-1]), -float(y))

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

    def serialize_liftboost(self):
        if self.liftboost is None:
            return [0,0,0,0]
        return [1, *self.liftboost]

    def serialize_wall(self):
        if self.wall is None: return 0
        if self.wall == 'WallL': return 1 
        if self.wall == 'WallR': return 2
        return 255

    def serialize_retained(self):
        if not self.retained:
            return [0,0,0]
        return [1, self.retain_frame, self.retain_value]

    def serialize(self):
        """
        boilerplate
        4i length
        8d timestamp
        = 12

        4i current_line
        4i current_frame_in_tas
        4i total_frames
        4i savestate_line
        4i tas_states
        = 20 -> 32

        4f xpos
        4f ypos
        4f xspeed
        4f yspeed
        4f xvel
        4f yvel
        = 24 -> 56

        4f stamina
        1i liftboost?
        2i liftboost frames
        4i liftboost x
        4i liftboost y
        1i retained?
        2i retain frame
        4i retain value
        = 22 -> 78

        1i wall (0 = None, 1 = L, 2 = R)
        4i frame
        = 5 -> 83

        states
            2i number
            1i kind
        = 2+N

        statuses
            2i number
            1i kind
            2i frames
        =2+3*N

        null terminated: room name
        =?

        """
        fmt = ( '=Id' #length and stamp
                +'iiiii' #cruft
                +'ffffff' #position and speed
                +'fBHffBHf' #stamina, liftboost, retained
                +'BI' #wall and frame
                )

        statefmt = 'H'+'B'*len(self.states)
        statusfmt = 'H'+'Bh'*len(self.statuses)

        fmt += statefmt
        fmt += statusfmt
        fmt += f'{len(self.room)+1}s'

        length = struct.calcsize(fmt)-4

        data = [length, self.stamp,
                self.current_line, self.current_frame_in_tas, self.total_frames, self.savestate_line, self.tas_states,
                *self.pos, *self.speed, *self.vel,
                self.stamina, *self.serialize_liftboost(), *self.serialize_retained(),
                self.serialize_wall(), self.frame
                ]

        data.append(len(self.states))
        for state in self.states:
            data.append(state_to_idx[state])

        data.append(len(self.statuses))
        for status in self.statuses:
            data.extend(status.serialize())

        data.append(self.room.encode('ascii'))

        result = struct.pack(fmt, *data)

        return result

if __name__ == '__main__':

    msgs = []
    start_time = time.time()
    infile = sys.argv[1]
    with open(infile, 'rb') as fp:
        idx = 0
        bad = 0
        weird = 0
        while True:
            try:
                msg= Message(fp)
                msgs.append(msg)
                idx += 1
                if idx%1000 ==0:
                    print(idx)
            except RuntimeError:
                break
            except IgnoreMessage:
                weird += 1
            except SerializationException:
                bad +=1


    print(f'{len(msgs)} messages processed. {bad} bad messages ignored. {weird} inscrutable messages ignored.')
    mid_time = time.time()
    print(f'msgs loaded in {mid_time-start_time:.2f} s')

    outfile = os.path.splitext(infile)[0]+'.bin'

    with open(outfile, 'wb') as fp:
        for msg in msgs:
            fp.write(msg.serialize())


    start_time = time.time()
    game_states = []
    with open(outfile, 'rb') as fp:
        while True:
            try:
                gs = GameState()
                gs.read(fp)
                game_states.append(gs)
            except RuntimeError:
                break
    end_time = time.time()
    print(f'{len(game_states)} game states loaded in {end_time-start_time:.2f} s')


