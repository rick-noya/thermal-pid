import tkinter as tk
from tkinter import ttk
from .utils import Tooltip

class ControlPanel(ttk.LabelFrame):
    def __init__(self, master, pid, siggen, set_status=None, style='TLabelframe', **kwargs):
        super().__init__(master, text="PID & Signal Generator Control", style=style, **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.set_status = set_status or (lambda msg: None) # Main app status
        self.columnconfigure(0, weight=1) # Make the main frame responsive

        # --- PID Controls Section ---
        pid_frame = ttk.Frame(self, padding=(5,5), style='Content.TFrame') # Use Content.TFrame if TLabelframe bg is different
        pid_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        # pid_frame.columnconfigure(tuple(range(4)), weight=1) # Distribute space within PID frame

        # Row 0: Setpoint
        ttk.Label(pid_frame, text="Setpoint (°C):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.setpoint_var = tk.DoubleVar(value=pid.setpoint)
        self.setpoint_spin = ttk.Spinbox(pid_frame, from_=0, to=200, increment=0.5, textvariable=self.setpoint_var, width=8)
        self.setpoint_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.setpoint_spin, "Target temperature for PID control.")

        # Row 1: PID Gains (Kp, Ki, Kd)
        gains_frame = ttk.Frame(pid_frame, style='Content.TFrame')
        gains_frame.grid(row=1, column=0, columnspan=4, sticky='ew', pady=5)

        ttk.Label(gains_frame, text="Kp:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.kp_var = tk.DoubleVar(value=pid.Kp)
        self.kp_spin = ttk.Spinbox(gains_frame, from_=0, to=100, increment=0.01, textvariable=self.kp_var, width=7)
        self.kp_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.kp_spin, "Proportional gain for PID controller.")

        ttk.Label(gains_frame, text="Ki:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=5, pady=2)
        self.ki_var = tk.DoubleVar(value=pid.Ki)
        self.ki_spin = ttk.Spinbox(gains_frame, from_=0, to=100, increment=0.01, textvariable=self.ki_var, width=7)
        self.ki_spin.grid(row=0, column=3, sticky='ew', padx=5, pady=2)
        Tooltip(self.ki_spin, "Integral gain for PID controller.")

        ttk.Label(gains_frame, text="Kd:", style='Content.TLabel').grid(row=0, column=4, sticky='w', padx=5, pady=2)
        self.kd_var = tk.DoubleVar(value=pid.Kd)
        self.kd_spin = ttk.Spinbox(gains_frame, from_=0, to=100, increment=0.01, textvariable=self.kd_var, width=7)
        self.kd_spin.grid(row=0, column=5, sticky='ew', padx=5, pady=2)
        Tooltip(self.kd_spin, "Derivative gain for PID controller.")
        for i in range(6): gains_frame.columnconfigure(i, weight=1, uniform="gains")

        # Row 2: PID Actions
        actions_frame = ttk.Frame(pid_frame, style='Content.TFrame')
        actions_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=5)

        self.update_pid_btn = ttk.Button(actions_frame, text="Update PID", command=self.update_pid)
        self.update_pid_btn.grid(row=0, column=0, padx=5, pady=2, sticky='ew')
        Tooltip(self.update_pid_btn, "Apply the current PID parameters.")

        self.pid_enable_var = tk.BooleanVar(value=True)
        self.enable_pid_chk = ttk.Checkbutton(actions_frame, text="Enable PID", variable=self.pid_enable_var, command=self.toggle_pid_controls)
        self.enable_pid_chk.grid(row=0, column=1, padx=5, pady=2, sticky='w')
        Tooltip(self.enable_pid_chk, "Enable or disable PID control.")

        self.start_pid_btn = ttk.Button(actions_frame, text="Start PID", command=self.start_ramp, style='Primary.TButton')
        self.start_pid_btn.grid(row=0, column=2, padx=5, pady=2, sticky='ew')
        Tooltip(self.start_pid_btn, "Start PID control loop.")

        self.stop_pid_btn = ttk.Button(actions_frame, text="Stop PID", command=self.stop_all)
        self.stop_pid_btn.grid(row=0, column=3, padx=5, pady=2, sticky='ew')
        Tooltip(self.stop_pid_btn, "Stop PID control and set output to 0V.")
        for i in range(4): actions_frame.columnconfigure(i, weight=1, uniform="actions")
        pid_frame.columnconfigure(0, weight=1)
        pid_frame.columnconfigure(1, weight=2) # Spinbox gets more space

        # --- Signal Generator Controls Section ---
        sg_frame = ttk.LabelFrame(self, text="Signal Generator", style='TLabelframe', padding=(5,5))
        sg_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=(10,5))
        sg_frame.columnconfigure(tuple(range(6)), weight=1, uniform="sg_uniform") # Allow responsive columns

        # Connection part
        ttk.Label(sg_frame, text="Port:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_port_var = tk.StringVar(value=self.siggen._port if self.siggen._port else "COM3")
        self.port_entry = ttk.Entry(sg_frame, textvariable=self.sg_port_var, width=12)
        self.port_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.port_entry, "Serial port for the signal generator (e.g., COM8 or /dev/ttyUSB0).")

        ttk.Label(sg_frame, text="Baud:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.sg_baud_var = tk.IntVar(value=self.siggen._baud if self.siggen._baud else 9600)
        self.baud_entry = ttk.Entry(sg_frame, textvariable=self.sg_baud_var, width=10)
        self.baud_entry.grid(row=0, column=3, sticky='ew', padx=5, pady=5)
        Tooltip(self.baud_entry, "Baud rate for the signal generator serial connection.")

        self.open_serial_btn = ttk.Button(sg_frame, text="Open", command=self.open_serial)
        self.open_serial_btn.grid(row=0, column=4, padx=5, pady=5, sticky='ew')
        Tooltip(self.open_serial_btn, "Open the serial port for the signal generator.")

        self.close_serial_btn = ttk.Button(sg_frame, text="Close", command=self.close_serial, state='disabled')
        self.close_serial_btn.grid(row=0, column=5, padx=5, pady=5, sticky='ew')
        Tooltip(self.close_serial_btn, "Close the serial port for the signal generator.")

        # Settings part (initially disabled)
        self.sg_settings_frame = ttk.Frame(sg_frame, style='Content.TFrame')
        self.sg_settings_frame.grid(row=1, column=0, columnspan=6, sticky='ew', pady=5)
        self.sg_settings_frame.columnconfigure(tuple(range(8)), weight=1, uniform="sg_settings")

        ttk.Label(self.sg_settings_frame, text="Frequency (Hz):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_freq_var = tk.DoubleVar(value=100000.0)
        self.freq_spin = ttk.Spinbox(self.sg_settings_frame, from_=0, to=1000000, increment=100, textvariable=self.sg_freq_var, width=10)
        self.freq_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.freq_spin, "Set the output frequency in Hz.")
        self.set_freq_btn = ttk.Button(self.sg_settings_frame, text="Set Freq", command=self.set_frequency)
        self.set_freq_btn.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        Tooltip(self.set_freq_btn, "Apply the frequency to the signal generator.")

        self.minus_freq_btn = ttk.Button(self.sg_settings_frame, text="-", command=self.decrease_freq, width=3)
        self.minus_freq_btn.grid(row=0, column=3, padx=2, pady=5, sticky='ew')
        Tooltip(self.minus_freq_btn, "Decrease frequency.")
        self.plus_freq_btn = ttk.Button(self.sg_settings_frame, text="+", command=self.increase_freq, width=3)
        self.plus_freq_btn.grid(row=0, column=4, padx=2, pady=5, sticky='ew')
        Tooltip(self.plus_freq_btn, "Increase frequency.")

        ttk.Label(self.sg_settings_frame, text="Voltage (V):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.sg_voltage_var = tk.DoubleVar(value=1.0)
        self.volt_spin = ttk.Spinbox(self.sg_settings_frame, from_=0, to=10, increment=0.01, textvariable=self.sg_voltage_var, width=8)
        self.volt_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.volt_spin, "Set the output voltage in volts.")
        self.set_volt_btn = ttk.Button(self.sg_settings_frame, text="Set Volt", command=self.set_voltage)
        self.set_volt_btn.grid(row=1, column=2, padx=5, pady=5, sticky='ew')
        Tooltip(self.set_volt_btn, "Apply the voltage to the signal generator.")

        self.output_on_btn = ttk.Button(self.sg_settings_frame, text="Output ON", command=self.output_on, style='Primary.TButton')
        self.output_on_btn.grid(row=1, column=3, columnspan=1, padx=5, pady=5, sticky='ew') # columnspan reduced for balance
        Tooltip(self.output_on_btn, "Enable the signal generator output.")
        self.output_off_btn = ttk.Button(self.sg_settings_frame, text="Output OFF", command=self.output_off)
        self.output_off_btn.grid(row=1, column=4, columnspan=1, padx=5, pady=5, sticky='ew')
        Tooltip(self.output_off_btn, "Disable the signal generator output.")

        # Raw command part (initially disabled)
        self.sg_raw_cmd_frame = ttk.Frame(sg_frame, style='Content.TFrame')
        self.sg_raw_cmd_frame.grid(row=2, column=0, columnspan=6, sticky='ew', pady=5)
        self.sg_raw_cmd_frame.columnconfigure(1, weight=1) # Entry expands

        ttk.Label(self.sg_raw_cmd_frame, text="Raw Cmd:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(self.sg_raw_cmd_frame, textvariable=self.sg_cmd_var, width=30)
        self.cmd_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)
        Tooltip(self.cmd_entry, "Send a raw command string to the signal generator.")
        self.send_cmd_btn = ttk.Button(self.sg_raw_cmd_frame, text="Send", command=self.send_cmd)
        self.send_cmd_btn.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        Tooltip(self.send_cmd_btn, "Send the raw command to the signal generator.")

        # Signal Generator Status Bar
        self.sg_status_var = tk.StringVar(value="Signal Generator Ready.")
        sg_status_label = ttk.Label(sg_frame, textvariable=self.sg_status_var, style='Status.TLabel', anchor='w', relief='flat', padding=(3,2))
        sg_status_label.grid(row=3, column=0, columnspan=6, sticky='ew', padx=5, pady=(5,2))

        # Group all SG controls that should be disabled/enabled together
        self.sg_interactive_widgets = [
            self.freq_spin, self.set_freq_btn, self.minus_freq_btn, self.plus_freq_btn,
            self.volt_spin, self.set_volt_btn, self.output_on_btn, self.output_off_btn,
            self.cmd_entry, self.send_cmd_btn
        ]
        self._toggle_sg_controls_enabled(False) # Initially disabled
        self.toggle_pid_controls() # Initial state based on checkbox

    def _toggle_sg_controls_enabled(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        for widget in self.sg_interactive_widgets:
            widget.configure(state=state)
        # Special handling for frames if they need to be hidden/shown or look disabled
        # For now, just disabling contents.

    def toggle_pid_controls(self):
        enabled = self.pid_enable_var.get()
        state = 'normal' if enabled else 'disabled'
        # Keep Update button always enabled to change params even if PID is not running
        self.start_pid_btn.configure(state=state)
        self.stop_pid_btn.configure(state=state if enabled else 'disabled') # Stop btn also disabled if PID disabled
        # Directly configure spinboxes
        self.setpoint_spin.configure(state=state)
        self.kp_spin.configure(state=state)
        self.ki_spin.configure(state=state)
        self.kd_spin.configure(state=state)
        # Update button should be enabled if PID is enabled, or if values can be set even if not running
        # For now, tied to PID enable state.
        self.update_pid_btn.configure(state=state)

    def open_serial(self):
        self.siggen._port = self.sg_port_var.get()
        self.siggen._baud = self.sg_baud_var.get()
        self.set_sg_status(f"Opening {self.siggen._port} at {self.siggen._baud} baud...")
        try:
            self.siggen.open()
            status_msg = f"Opened {self.siggen._port} at {self.siggen._baud} baud."
            self.set_status(status_msg) # Main status
            self.set_sg_status(status_msg) # SG status
            self.open_serial_btn.configure(state='disabled')
            self.close_serial_btn.configure(state='normal')
            self.port_entry.configure(state='disabled')
            self.baud_entry.configure(state='disabled')
            self._toggle_sg_controls_enabled(True)
        except Exception as e:
            error_msg = f"Error opening serial: {e}"
            self.set_status(error_msg) # Main status
            self.set_sg_status(error_msg) # SG status
            # Ensure sg controls remain disabled if open fails
            self._toggle_sg_controls_enabled(False)

    def close_serial(self):
        self.set_sg_status("Closing serial port...")
        try:
            self.siggen.close()
            status_msg = "Serial port closed."
            self.set_status(status_msg)
            self.set_sg_status(status_msg)
            self.open_serial_btn.configure(state='normal')
            self.close_serial_btn.configure(state='disabled')
            self.port_entry.configure(state='normal')
            self.baud_entry.configure(state='normal')
            self._toggle_sg_controls_enabled(False)
        except Exception as e:
            error_msg = f"Error closing serial: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def update_pid(self):
        if not self.pid_enable_var.get(): # Check if PID is enabled
            self.set_status("PID is disabled. Enable to update parameters.")
            return
        try:
            self.pid.update_tunings(self.kp_var.get(), self.ki_var.get(), self.kd_var.get())
            self.pid.update_setpoint(self.setpoint_var.get())
            self.set_status("PID parameters updated.")
        except tk.TclError as e:
            self.set_status(f"PID Update Error: Invalid value. {e}")
        except Exception as e:
            self.set_status(f"PID Update Error: {e}")

    def start_ramp(self):
        if not self.pid_enable_var.get():
            self.set_status("PID is disabled. Cannot start.")
            return
        self.update_pid() # Ensure latest params are set before starting
        self.pid.resume()
        self.set_status("PID control started.")
        # Potentially disable start, enable stop, etc.
        self.start_pid_btn.configure(state='disabled')
        self.stop_pid_btn.configure(state='normal')
        self.enable_pid_chk.configure(state='disabled') # Disable checkbox while running

    def stop_all(self):
        self.pid.pause()
        self.set_status("PID control stopped.")
        # Potentially disable stop, enable start
        self.start_pid_btn.configure(state='normal')
        self.stop_pid_btn.configure(state='disabled')
        self.enable_pid_chk.configure(state='normal') # Re-enable checkbox
        try:
            if self.siggen.is_open:
                self.siggen.set_voltage(0.0) # Ensure voltage is set to 0 on stop
                self.siggen.output_off()      # Ensure output is off
                self.set_status("PID stopped. SigGen output set to 0V and OFF.")
        except Exception as e:
            self.set_status(f"PID stopped. SigGen error: {e}")

    # ... (rest of the Signal Generator methods: set_frequency, increase_freq, etc.)
    # These should check if self.siggen.is_open before acting, or rely on controls being disabled.
    # Adding a check here for robustness.

    def _check_serial_open(self):
        if not self.siggen.is_open:
            # self.set_status("Serial port not open.") # Main status might be too noisy for this check
            self.set_sg_status("Serial port not open. Please open port first.")
            return False
        return True

    def set_frequency(self):
        if not self._check_serial_open(): return
        try:
            freq = int(self.sg_freq_var.get())
            self.siggen.set_frequency(freq)
            status_msg = f"Frequency set to {freq} Hz"
            self.set_sg_status(status_msg)
            # self.set_status(status_msg) # Optionally update main status too
        except Exception as e:
            error_msg = f"Freq error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def increase_freq(self):
        if not self._check_serial_open(): return
        try:
            current_val = self.sg_freq_var.get()
            freq = int(current_val) + int(self.freq_spin.cget('increment')) # use configured increment
            self.sg_freq_var.set(freq)
            self.set_frequency()
        except Exception as e:
            self.set_status(f"Freq error: {e}")

    def decrease_freq(self):
        if not self._check_serial_open(): return
        try:
            current_val = self.sg_freq_var.get()
            freq = max(0, int(current_val) - int(self.freq_spin.cget('increment')))
            self.sg_freq_var.set(freq)
            self.set_frequency()
        except Exception as e:
            self.set_status(f"Freq error: {e}")

    def set_voltage(self):
        if not self._check_serial_open(): return
        try:
            voltage = float(self.sg_voltage_var.get())
            self.siggen.set_voltage(voltage)
            status_msg = f"Voltage set to {voltage:.2f} V"
            self.set_sg_status(status_msg)
            # self.set_status(status_msg)
        except Exception as e:
            error_msg = f"Volt error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def output_on(self):
        if not self._check_serial_open(): return
        try:
            self.siggen.output_on()
            status_msg = "Signal Generator Output ON"
            self.set_sg_status(status_msg)
            self.set_status(status_msg) # Also to main status as it's an important state change
            self.output_on_btn.configure(state='disabled')
            self.output_off_btn.configure(state='normal')
        except Exception as e:
            error_msg = f"ON error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def output_off(self):
        if not self._check_serial_open(): return
        try:
            self.siggen.output_off()
            status_msg = "Signal Generator Output OFF"
            self.set_sg_status(status_msg)
            self.set_status(status_msg) # Also to main status
            self.output_on_btn.configure(state='normal')
            self.output_off_btn.configure(state='disabled')
        except Exception as e:
            error_msg = f"OFF error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def send_cmd(self):
        if not self._check_serial_open(): return
        cmd = self.sg_cmd_var.get()
        if not cmd:
            self.set_sg_status("Command empty. Type a command to send.")
            return
        try:
            resp = self.siggen.raw_command(cmd)
            status_msg = f"Cmd: '{cmd}' -> Resp: {resp if resp else 'OK'}"
            self.set_sg_status(status_msg)
            # self.set_status(status_msg) # Maybe too verbose for main status
            self.sg_cmd_var.set("") # Clear after send
        except Exception as e:
            error_msg = f"Cmd '{cmd}' error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def set_sg_status(self, msg):
        self.sg_status_var.set(msg)