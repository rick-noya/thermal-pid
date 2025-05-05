from simple_pid import PID

class TemperaturePID(PID):
    """Adds sane defaults, typed helpers and pause/resume for temperature control."""
    def __init__(self, kp=1.0, ki=0.1, kd=0.05, setpoint=60.0, v_limits=(0.0, 10.0)):
        super().__init__(kp, ki, kd, setpoint=setpoint, output_limits=v_limits, sample_time=0.1)

    def pause(self):
        self.auto_mode = False

    def resume(self):
        self.auto_mode = True

    def update_tunings(self, kp, ki, kd):
        self.tunings = (kp, ki, kd)

    def update_setpoint(self, setpoint):
        self.setpoint = setpoint 