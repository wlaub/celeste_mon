import struct

from model import MessageId, state_to_idx, status_to_idx, states, statuses, Status


class GameState:
    def __init__(self):
        pass

    def read(self, fp):
        length_raw = fp.read(4)
        if len(length_raw) == 0:
            raise RuntimeError('Done')

        length = struct.unpack('I', length_raw)[0]
        raw_data = fp.read(length)

        self.deserialize(raw_data)

    def deserialize(self, raw):
    
        head_fmt = ( '=d' #stamp
                +'iiiii' #cruft
                +'ffffff' #position and speed
                +'fBHffBHf' #stamina, liftboost, retained
                +'BI' #wall and frame
                )

        head_len = struct.calcsize(head_fmt)
        head_raw = raw[:head_len]
        offset = head_len

        state_count = struct.unpack('H', raw[offset:offset+2])[0]
        state_len = state_count
        offset += 2

        state_fmt = '='+'B'*state_count
        state_raw = raw[offset:offset+state_len]
        offset += state_len

        status_count = struct.unpack('H', raw[offset:offset+2])[0]
        offset += 2

        status_fmt = '='+'Bh'*status_count
        status_len = status_count*3
        status_raw = raw[offset:offset+status_len]
        offset += status_len


        self.room = raw[offset:-1].decode('ascii')

        #deserialize head
        head_data = struct.unpack(head_fmt, head_raw)
        self.stamp = head_data[0]
        self.pos = head_data[6:8]
        self.speed = head_data[8:10]
        self.vel = head_data[10:12]
        self.stamina = head_data[12]
        self.liftboost = head_data[13:17]
        self.retained = head_data[17:20]
        self.wall = head_data[20]
        self.frame = head_data[21]

        #deserialize state
        state_indices = struct.unpack(state_fmt, state_raw)
        self.states = {idx_to_state[x] for x in state_indices}

        #deserialize status
        self.statuses = []
        status_indices = struct.unpack(status_fmt, status_raw)
        for idx in range(status_count):
            st = Status(*status_indices[idx*2:idx*2+2])
            self.statuses.append(st)


