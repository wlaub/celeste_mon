import enum

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

idx_to_state = dict(enumerate(states))
state_to_idx = {v:k for k,v in idx_to_state.items()}

statuses = [
'Frozen',
'Coyote',
'Jump',
'MaxFall',
'NoControl',
'CanDash',
'DashCD',
'CantPause',
'Dead',
'Cutscene',
'Grab',
'Berry',
'ForceMoveR',
'ForceMoveL',
'ForceMoveN',
]

idx_to_status = dict(enumerate(statuses))
status_to_idx = {v:k for k,v in idx_to_status.items()}

class Status:
    def __init__(self, idx, frames):
        self.status = idx_to_status[idx]
        self.frames = frames

    @staticmethod
    def parse(raw):
        self = Status(0,0)
        self.frames = -1
        if '(' in raw:
            self.parse_frame_status(raw)
        else:
            self.status = raw

        if not self.status in statuses:
            print(raw)

        return self

    def parse_frame_status(self, raw):
        name, frames = raw.split('(')
        frames = int(frames.split(')')[0])
        self.status = name
        self.frames = frames

    def serialize(self):
        return [status_to_idx[self.status], self.frames]

    def __repr__(self):
        if self.frames >= 0:
            return f'{self.status}({self.frames})'
        else:
            return f'{self.status}'

