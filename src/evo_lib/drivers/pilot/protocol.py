"""Binary protocol for the carte-asserv (motor control board).

Packet format: [LENGTH, COMMAND_ID, PARAMS...]
- LENGTH includes itself (minimum 2 for an empty command)
- PARAMS are struct.pack'd values
"""

import struct
from enum import IntEnum


class Commands(IntEnum):
    # Query
    GET_TRAVEL_THETA = 2
    GET_PID_TRSL = 10
    GET_PID_ROT = 11
    GET_POSITION = 12
    GET_SPEEDS = 13
    GET_WHEELS = 14
    GET_DELTA_MAX = 15
    GET_VECTOR_TRSL = 16
    GET_VECTOR_ROT = 17

    # Movement
    GOTO_XY = 100
    GOTO_THETA = 101
    MOVE_TRSL = 102
    MOVE_ROT = 103
    GLOBAL_GOTO = 105  # Holonomic: go to (x,y,theta) with timing percentages

    # Control
    UNFREE = 108
    FREE = 109
    RECALAGE = 110
    SET_PWM = 111
    STOP_ASAP = 112

    # Events (received from board)
    DEBUG = 126
    DEBUG_MESSAGE = 127
    MOVE_BEGIN = 128
    MOVE_END = 129

    # Configuration
    SET_PID_TRSL = 150
    SET_PID_ROT = 151
    SET_TRSL_ACC = 152
    SET_TRSL_DEC = 153
    SET_TRSL_MAXSPEED = 154
    SET_ROT_ACC = 155
    SET_ROT_DEC = 156
    SET_ROT_MAXSPEED = 157
    SET_X = 158
    SET_Y = 159
    SET_THETA = 160
    SET_WHEELS_DIAM = 161
    SET_WHEELS_SPACING = 162
    SET_DELTA_MAX_ROT = 163
    SET_DELTA_MAX_TRSL = 164
    SET_ROBOT_SIZE_X = 165
    SET_ROBOT_SIZE_Y = 166
    OTOS_CAL = 167  # Optical tracking sensor calibration (holonomic)

    # Telemetry
    ACKNOWLEDGE = 200
    SET_TELEMETRY = 201
    TELEMETRY_MESSAGE = 202

    # Error
    INIT = 254
    ERROR = 255


class Errors(IntEnum):
    COULD_NOT_READ = 1
    DESTINATION_UNREACHABLE = 2
    BAD_ORDER = 3


# Commands that do not expect an ACK from the board (from firmware trajman_commands.h)
NO_ACK_COMMANDS: set[Commands] = {
    Commands.SET_PWM,
    Commands.GET_PID_TRSL,
    Commands.GET_PID_ROT,
    Commands.GET_POSITION,
    Commands.GET_SPEEDS,
    Commands.GET_WHEELS,
    Commands.GET_DELTA_MAX,
    Commands.GET_VECTOR_TRSL,
    Commands.GET_VECTOR_ROT,
    Commands.GET_TRAVEL_THETA,
}

# Init sequence: magic bytes to synchronize with the board
INIT_PACKET = bytes([5, Commands.INIT, 0xAA, 0xAA, 0xAA])

# Struct formats for commands (little-endian on RPi, matches firmware)
FORMATS: dict[Commands, str] = {
    # Movement
    Commands.GOTO_XY: "ff",
    Commands.GOTO_THETA: "f",
    Commands.MOVE_TRSL: "ffffb",
    Commands.MOVE_ROT: "ffffb",
    # x, y, theta, rot_start, rot_end, trsl_start, trsl_end (0.0-1.0), rot_dir, avoid
    Commands.GLOBAL_GOTO: "fffffffbb",
    Commands.UNFREE: "",
    Commands.FREE: "",
    Commands.STOP_ASAP: "ff",
    Commands.RECALAGE: "BfB",  # direction, offset, set
    Commands.SET_PWM: "ff",
    # Position
    Commands.SET_X: "f",
    Commands.SET_Y: "f",
    Commands.SET_THETA: "f",
    # PID
    Commands.SET_PID_TRSL: "fff",
    Commands.SET_PID_ROT: "fff",
    # Speed limits
    Commands.SET_TRSL_ACC: "f",
    Commands.SET_TRSL_DEC: "f",
    Commands.SET_TRSL_MAXSPEED: "f",
    Commands.SET_ROT_ACC: "f",
    Commands.SET_ROT_DEC: "f",
    Commands.SET_ROT_MAXSPEED: "f",
    # Mechanical
    Commands.SET_WHEELS_DIAM: "ff",
    Commands.SET_WHEELS_SPACING: "f",
    Commands.SET_DELTA_MAX_ROT: "f",
    Commands.SET_DELTA_MAX_TRSL: "f",
    Commands.SET_ROBOT_SIZE_X: "f",
    Commands.SET_ROBOT_SIZE_Y: "f",
    # Telemetry
    Commands.SET_TELEMETRY: "H",
    # Calibration
    Commands.OTOS_CAL: "",
    # Queries (no params)
    Commands.GET_TRAVEL_THETA: "",
    Commands.GET_PID_TRSL: "",
    Commands.GET_PID_ROT: "",
    Commands.GET_POSITION: "",
    Commands.GET_SPEEDS: "",
    Commands.GET_WHEELS: "",
    Commands.GET_DELTA_MAX: "",
    Commands.GET_VECTOR_TRSL: "",
    Commands.GET_VECTOR_ROT: "",
}

# Struct formats for responses to GET commands (payload after bb header)
RESPONSE_FORMATS: dict[Commands, str] = {
    Commands.GET_PID_TRSL: "fff",  # kp, ki, kd
    Commands.GET_PID_ROT: "fff",  # kp, ki, kd
    Commands.GET_POSITION: "fff",  # x, y, theta
    Commands.GET_SPEEDS: "ffffff",  # trsl_acc, trsl_dec, trsl_max, rot_acc, rot_dec, rot_max
    Commands.GET_WHEELS: "fff",  # spacing, diam_left, diam_right
    Commands.GET_DELTA_MAX: "ff",  # trsl, rot
    Commands.GET_VECTOR_TRSL: "f",  # translation speed
    Commands.GET_VECTOR_ROT: "f",  # rotation speed
    Commands.GET_TRAVEL_THETA: "f",  # travel direction (rad)
}


def build_packet(command: Commands, *args) -> bytes:
    """Build a binary packet for the carte-asserv.

    Returns bytes: [LENGTH, COMMAND_ID, PACKED_PARAMS...]
    """
    fmt = FORMATS.get(command, "")
    if fmt:
        params = struct.pack(fmt, *args)
    else:
        params = b""
    length = 2 + len(params)  # length byte + command byte + params
    return bytes([length, command]) + params
