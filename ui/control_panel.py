import tkinter as tk
from tkinter import ttk

# Robust tooltip helper for Tkinter/ttk widgets
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        widget.bind("<Enter>", self.enter)
        widget.bind("<Leave>", self.leave)
        widget.bind("<Motion>", self.motion)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def motion(self, event):
        self.x = event.x_root + 20
        self.y = event.y_root + 10
        if self.tipwindow:
            self.tipwindow.wm_geometry(f"+{self.x}+{self.y}")

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self):
        if self.tipwindow or not self.text:
            return
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{self.x}+{self.y}")
        label = tk.Label(
            tw, text=self.text, justify='left',
            background="#ffffe0", relief='solid', borderwidth=1,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=4, ipady=2)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class ControlPanel(ttk.LabelFrame):
    def __init__(self, master, pid, siggen, set_status=None, **kwargs):
        super().__init__(master, text="PID & Signal Generator Control", **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.set_status = set_status or (lambda msg: None)

        # PID Controls
        ttk.Label(self, text="Setpoint (°C):").grid(row=0, column=0, sticky='e', padx=2, pady=2)
        self.setpoint_var = tk.DoubleVar(value=pid.setpoint)
        setpoint_spin = ttk.Spinbox(self, from_=0, to=200, increment=0.5, textvariable=self.setpoint_var, width=6)
        setpoint_spin.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        Tooltip(setpoint_spin, "Target temperature for PID control.")

        ttk.Label(self, text="Kp:").grid(row=0, column=2, sticky='e', padx=2, pady=2)
        self.kp_var = tk.DoubleVar(value=pid.Kp)
        kp_spin = ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.kp_var, width=5)
        kp_spin.grid(row=0, column=3, sticky='ew', padx=2, pady=2)
        Tooltip(kp_spin, "Proportional gain for PID controller.")

        ttk.Label(self, text="Ki:").grid(row=0, column=4, sticky='e', padx=2, pady=2)
        self.ki_var = tk.DoubleVar(value=pid.Ki)
        ki_spin = ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.ki_var, width=5)
        ki_spin.grid(row=0, column=5, sticky='ew', padx=2, pady=2)
        Tooltip(ki_spin, "Integral gain for PID controller.")

        ttk.Label(self, text="Kd:").grid(row=0, column=6, sticky='e', padx=2, pady=2)
        self.kd_var = tk.DoubleVar(value=pid.Kd)
        kd_spin = ttk.Spinbox(self, from_=0, to=10, increment=0.01, textvariable=self.kd_var, width=5)
        kd_spin.grid(row=0, column=7, sticky='ew', padx=2, pady=2)
        Tooltip(kd_spin, "Derivative gain for PID controller.")

        update_btn = ttk.Button(self, text="Update PID", command=self.update_pid)
        update_btn.grid(row=0, column=8, padx=6, pady=2, sticky='ew')
        Tooltip(update_btn, "Apply the current PID parameters.")

        self.pid_enable_var = tk.BooleanVar(value=True)
        enable_chk = ttk.Checkbutton(self, text="Enable PID", variable=self.pid_enable_var)
        enable_chk.grid(row=0, column=9, padx=2, pady=2, sticky='ew')
        Tooltip(enable_chk, "Enable or disable PID control.")

        start_btn = ttk.Button(self, text="Start", command=self.start_ramp)
        start_btn.grid(row=0, column=10, padx=6, pady=2, sticky='ew')
        Tooltip(start_btn, "Start PID control loop.")

        stop_btn = ttk.Button(self, text="Stop", command=self.stop_all)
        stop_btn.grid(row=0, column=11, padx=6, pady=2, sticky='ew')
        Tooltip(stop_btn, "Stop PID control and set output to 0V.")

        # Signal Generator Controls
        sg_frame = ttk.LabelFrame(self, text="Signal Generator")
        sg_frame.grid(row=1, column=0, columnspan=12, sticky='ew', padx=2, pady=(8,2))
        sg_frame.columnconfigure(tuple(range(10)), weight=1)

        ttk.Label(sg_frame, text="Port:").grid(row=0, column=0, sticky='e', padx=2, pady=2)
        self.sg_port_var = tk.StringVar(value=self.siggen._port)
        port_entry = ttk.Entry(sg_frame, textvariable=self.sg_port_var, width=10)
        port_entry.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        Tooltip(port_entry, "Serial port for the signal generator (e.g., COM8).")

        ttk.Label(sg_frame, text="Baud:").grid(row=0, column=2, sticky='e', padx=2, pady=2)
        self.sg_baud_var = tk.IntVar(value=self.siggen._baud)
        baud_entry = ttk.Entry(sg_frame, textvariable=self.sg_baud_var, width=8)
        baud_entry.grid(row=0, column=3, sticky='ew', padx=2, pady=2)
        Tooltip(baud_entry, "Baud rate for the signal generator serial connection.")

        open_btn = ttk.Button(sg_frame, text="Open", command=self.open_serial)
        open_btn.grid(row=0, column=4, padx=2, pady=2, sticky='ew')
        Tooltip(open_btn, "Open the serial port for the signal generator.")

        close_btn = ttk.Button(sg_frame, text="Close", command=self.close_serial)
        close_btn.grid(row=0, column=5, padx=2, pady=2, sticky='ew')
        Tooltip(close_btn, "Close the serial port for the signal generator.")

        ttk.Label(sg_frame, text="Frequency (Hz):").grid(row=1, column=0, sticky='e', padx=2, pady=2)
        self.sg_freq_var = tk.DoubleVar(value=100000.0)
        freq_spin = ttk.Spinbox(sg_frame, from_=0, to=100000, increment=1, textvariable=self.sg_freq_var, width=10)
        freq_spin.grid(row=1, column=1, sticky='ew', padx=2, pady=2)
        Tooltip(freq_spin, "Set the output frequency in Hz.")

        set_freq_btn = ttk.Button(sg_frame, text="Set Frequency", command=self.set_frequency)
        set_freq_btn.grid(row=1, column=2, padx=2, pady=2, sticky='ew')
        Tooltip(set_freq_btn, "Apply the frequency to the signal generator.")

        minus_btn = ttk.Button(sg_frame, text="-", command=self.decrease_freq, width=2)
        minus_btn.grid(row=1, column=3, padx=2, pady=2, sticky='ew')
        Tooltip(minus_btn, "Decrease frequency by 100 Hz.")

        plus_btn = ttk.Button(sg_frame, text="+", command=self.increase_freq, width=2)
        plus_btn.grid(row=1, column=4, padx=2, pady=2, sticky='ew')
        Tooltip(plus_btn, "Increase frequency by 100 Hz.")

        ttk.Label(sg_frame, text="Voltage (V):").grid(row=1, column=5, sticky='e', padx=2, pady=2)
        self.sg_voltage_var = tk.DoubleVar(value=1.0)
        volt_spin = ttk.Spinbox(sg_frame, from_=0, to=10, increment=0.01, textvariable=self.sg_voltage_var, width=8)
        volt_spin.grid(row=1, column=6, sticky='ew', padx=2, pady=2)
        Tooltip(volt_spin, "Set the output voltage in volts.")

        set_volt_btn = ttk.Button(sg_frame, text="Set Voltage", command=self.set_voltage)
        set_volt_btn.grid(row=1, column=7, padx=2, pady=2, sticky='ew')
        Tooltip(set_volt_btn, "Apply the voltage to the signal generator.")

        on_btn = ttk.Button(sg_frame, text="Output ON", command=self.output_on)
        on_btn.grid(row=1, column=8, padx=2, pady=2, sticky='ew')
        Tooltip(on_btn, "Enable the signal generator output.")

        off_btn = ttk.Button(sg_frame, text="Output OFF", command=self.output_off)
        off_btn.grid(row=1, column=9, padx=2, pady=2, sticky='ew')
        Tooltip(off_btn, "Disable the signal generator output.")

        ttk.Label(sg_frame, text="Raw Cmd:").grid(row=2, column=0, sticky='e', padx=2, pady=2)
        self.sg_cmd_var = tk.StringVar()
        cmd_entry = ttk.Entry(sg_frame, textvariable=self.sg_cmd_var, width=20)
        cmd_entry.grid(row=2, column=1, columnspan=3, sticky='ew', padx=2, pady=2)
        Tooltip(cmd_entry, "Send a raw command string to the signal generator.")

        send_btn = ttk.Button(sg_frame, text="Send", command=self.send_cmd)
        send_btn.grid(row=2, column=4, padx=2, pady=2, sticky='ew')
        Tooltip(send_btn, "Send the raw command to the signal generator.")

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