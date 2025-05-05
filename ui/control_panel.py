import tkinter as tk
from tkinter import ttk

class ControlPanel(ttk.LabelFrame):
    def __init__(self, master, pid, siggen, set_status=None, **kwargs):
        super().__init__(master, text="PID & Signal Generator Control", **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.set_status = set_status or (lambda msg: None)

        # PID Controls
        ttk.Label(self, text="Setpoint (°C):").grid(row=0, column=0, sticky='e', padx=2, pady=2)
        self.setpoint_var = tk.DoubleVar(value=pid.setpoint)
        ttk.Spinbox(self, from_=0, to=200, increment=0.5, textvariable=self.setpoint_var, width=6).grid(row=0, column=1, sticky='ew', padx=2, pady=2)

        ttk.Label(self, text="Kp:").grid(row=0, column=2, sticky='e', padx=2, pady=2)
        self.kp_var = tk.DoubleVar(value=pid.Kp)
        ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.kp_var, width=5).grid(row=0, column=3, sticky='ew', padx=2, pady=2)

        ttk.Label(self, text="Ki:").grid(row=0, column=4, sticky='e', padx=2, pady=2)
        self.ki_var = tk.DoubleVar(value=pid.Ki)
        ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.ki_var, width=5).grid(row=0, column=5, sticky='ew', padx=2, pady=2)

        ttk.Label(self, text="Kd:").grid(row=0, column=6, sticky='e', padx=2, pady=2)
        self.kd_var = tk.DoubleVar(value=pid.Kd)
        ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.kd_var, width=5).grid(row=0, column=7, sticky='ew', padx=2, pady=2)

        ttk.Button(self, text="Update PID", command=self.update_pid).grid(row=0, column=8, padx=6, pady=2, sticky='ew')
        self.pid_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Enable PID", variable=self.pid_enable_var).grid(row=0, column=9, padx=2, pady=2, sticky='ew')
        ttk.Button(self, text="Start", command=self.start_ramp).grid(row=0, column=10, padx=6, pady=2, sticky='ew')
        ttk.Button(self, text="Stop", command=self.stop_all).grid(row=0, column=11, padx=6, pady=2, sticky='ew')

        # Signal Generator Controls
        sg_frame = ttk.LabelFrame(self, text="Signal Generator")
        sg_frame.grid(row=1, column=0, columnspan=12, sticky='ew', padx=2, pady=(8,2))
        sg_frame.columnconfigure(tuple(range(10)), weight=1)

        ttk.Label(sg_frame, text="Port:").grid(row=0, column=0, sticky='e', padx=2, pady=2)
        self.sg_port_var = tk.StringVar(value=self.siggen._port)
        ttk.Entry(sg_frame, textvariable=self.sg_port_var, width=10).grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        ttk.Label(sg_frame, text="Baud:").grid(row=0, column=2, sticky='e', padx=2, pady=2)
        self.sg_baud_var = tk.IntVar(value=self.siggen._baud)
        ttk.Entry(sg_frame, textvariable=self.sg_baud_var, width=8).grid(row=0, column=3, sticky='ew', padx=2, pady=2)
        ttk.Button(sg_frame, text="Open", command=self.open_serial).grid(row=0, column=4, padx=2, pady=2, sticky='ew')
        ttk.Button(sg_frame, text="Close", command=self.close_serial).grid(row=0, column=5, padx=2, pady=2, sticky='ew')

        ttk.Label(sg_frame, text="Frequency (Hz):").grid(row=1, column=0, sticky='e', padx=2, pady=2)
        self.sg_freq_var = tk.DoubleVar(value=100000.0)
        ttk.Spinbox(sg_frame, from_=0, to=100000, increment=1, textvariable=self.sg_freq_var, width=10).grid(row=1, column=1, sticky='ew', padx=2, pady=2)
        ttk.Button(sg_frame, text="Set Frequency", command=self.set_frequency).grid(row=1, column=2, padx=2, pady=2, sticky='ew')
        ttk.Button(sg_frame, text="-", command=self.decrease_freq, width=2).grid(row=1, column=3, padx=2, pady=2, sticky='ew')
        ttk.Button(sg_frame, text="+", command=self.increase_freq, width=2).grid(row=1, column=4, padx=2, pady=2, sticky='ew')

        ttk.Label(sg_frame, text="Voltage (V):").grid(row=1, column=5, sticky='e', padx=2, pady=2)
        self.sg_voltage_var = tk.DoubleVar(value=1.0)
        ttk.Spinbox(sg_frame, from_=0, to=10, increment=0.01, textvariable=self.sg_voltage_var, width=8).grid(row=1, column=6, sticky='ew', padx=2, pady=2)
        ttk.Button(sg_frame, text="Set Voltage", command=self.set_voltage).grid(row=1, column=7, padx=2, pady=2, sticky='ew')
        ttk.Button(sg_frame, text="Output ON", command=self.output_on).grid(row=1, column=8, padx=2, pady=2, sticky='ew')
        ttk.Button(sg_frame, text="Output OFF", command=self.output_off).grid(row=1, column=9, padx=2, pady=2, sticky='ew')

        ttk.Label(sg_frame, text="Raw Cmd:").grid(row=2, column=0, sticky='e', padx=2, pady=2)
        self.sg_cmd_var = tk.StringVar()
        ttk.Entry(sg_frame, textvariable=self.sg_cmd_var, width=20).grid(row=2, column=1, columnspan=3, sticky='ew', padx=2, pady=2)
        ttk.Button(sg_frame, text="Send", command=self.send_cmd).grid(row=2, column=4, padx=2, pady=2, sticky='ew')

        # Make main frame responsive
        for i in range(12):
            self.columnconfigure(i, weight=1)
        self.rowconfigure(1, weight=1)

    def open_serial(self):
        self.siggen._port = self.sg_port_var.get()
        self.siggen._baud = self.sg_baud_var.get()
        try:
            self.siggen.open()
            self.set_status(f"Opened {self.siggen._port} at {self.siggen._baud}")
        except Exception as e:
            self.set_status(f"Open failed: {e}")

    def close_serial(self):
        try:
            self.siggen.close()
            self.set_status("Serial closed.")
        except Exception as e:
            self.set_status(f"Close failed: {e}")

    def set_frequency(self):
        try:
            freq = int(self.sg_freq_var.get())
            self.siggen.set_frequency(freq)
            self.set_status(f"Frequency set to {freq} Hz")
        except Exception as e:
            self.set_status(f"Freq error: {e}")

    def increase_freq(self):
        try:
            freq = int(self.sg_freq_var.get()) + 100
            self.sg_freq_var.set(freq)
            self.set_frequency()
        except Exception as e:
            self.set_status(f"Freq error: {e}")

    def decrease_freq(self):
        try:
            freq = max(0, int(self.sg_freq_var.get()) - 100)
            self.sg_freq_var.set(freq)
            self.set_frequency()
        except Exception as e:
            self.set_status(f"Freq error: {e}")

    def set_voltage(self):
        try:
            voltage = float(self.sg_voltage_var.get())
            self.siggen.set_voltage(voltage)
            self.set_status(f"Voltage set to {voltage:.2f} V")
        except Exception as e:
            self.set_status(f"Volt error: {e}")

    def output_on(self):
        try:
            self.siggen.output_on()
            self.set_status("Output ON")
        except Exception as e:
            self.set_status(f"ON error: {e}")

    def output_off(self):
        try:
            self.siggen.output_off()
            self.set_status("Output OFF")
        except Exception as e:
            self.set_status(f"OFF error: {e}")

    def send_cmd(self):
        cmd = self.sg_cmd_var.get()
        try:
            resp = self.siggen.raw_command(cmd)
            self.set_status(f"Resp: {resp}")
        except Exception as e:
            self.set_status(f"Cmd error: {e}")

    def update_pid(self):
        self.pid.update_tunings(self.kp_var.get(), self.ki_var.get(), self.kd_var.get())
        self.pid.update_setpoint(self.setpoint_var.get())

    def start_ramp(self):
        self.pid.resume()
        # You may want to add more logic here (e.g., UI feedback)

    def stop_all(self):
        self.pid.pause()
        # Optionally set output to 0V via siggen
        try:
            self.siggen.set_voltage(0.0)
            self.set_status("Output set to 0V (STOP)")
        except Exception:
            pass 