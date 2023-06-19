import time
import sys
import struct
import mmap
import enum
import re
import itertools

try:
    last_sequence = None
    with open('/tmp/celeste_tuw.share', 'r+b') as fx:
        with mmap.mmap(fx.fileno(), 0) as fp:
            while True:
                time.sleep(0.1)
                fp.seek(0)
                size_raw = fp.read(2)
                size = struct.unpack('=H', size_raw)[0]

                if size == 0:
                    continue

                raw = fp.read(size)

                sequence, timestamp, gametime, deaths = struct.unpack('=Idqi', raw[:24])
                raw = raw[24:]

                if sequence == last_sequence:
                    continue
                last_sequence = sequence

                room, raw = raw.split(b'\x00', maxsplit=1)
                room = room.decode('ascii')

                player_state_fmt = '=fffffffiiBB'
                size = struct.calcsize(player_state_fmt)
                player_state = struct.unpack(player_state_fmt, raw[:size])
                raw = raw[size:]
                (xpos, ypos, xvel, yvel, samina, xlift, ylift, state, dashes, control, status) = player_state

                input_state_fmt = '=BBff'
                size = struct.calcsize(input_state_fmt)
                input_state = struct.unpack(input_state_fmt, raw[:size])
                raw = raw[size:]

                print(sequence, timestamp, gametime, deaths, room)
                print(player_state)
                print(input_state)
                print()


except KeyboardInterrupt:
    pass



