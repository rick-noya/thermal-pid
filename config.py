# Central configuration for the thermal PID controller project

STREAM_FPS = 15
DEFAULT_PORT_CAM = "COM9"
DEFAULT_PORT_SIGGEN = "COM8"
SIGGEN_BAUD = 115200
SIGGEN_TIMEOUT = 1.0

PID_DEFAULTS = dict(kp=1.0, ki=0.1, kd=0.05, setpoint=60.0, v_limits=(0.0, 5.0)) 