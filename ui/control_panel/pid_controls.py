import tkinter as tk
from tkinter import ttk
from ..utils import Tooltip
import config

class PIDControls(ttk.LabelFrame):
    """
    UI component for PID parameter controls and logic.
    Callbacks:
        on_start: Called after PID is started.
        on_stop: Called after PID is stopped.
    """
    def __init__(self, master, pid, set_status=None, style='TLabelframe', max_voltage_var=None, on_start=None, on_stop=None, **kwargs):
        super().__init__(master, text="PID Parameters", style=style, **kwargs)
        self.pid = pid
        self.set_status = set_status or (lambda msg: None)
        self.max_voltage_var = max_voltage_var
        self._save_on_setpoint_triggered = False
        self.on_start = on_start
        self.on_stop = on_stop

        # Row 0: Setpoint
        ttk.Label(self, text="Setpoint (°C):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.setpoint_var = tk.DoubleVar(value=pid.setpoint)
        self.setpoint_spin = ttk.Spinbox(self, from_=0, to=200, increment=0.5, textvariable=self.setpoint_var, width=8)
        self.setpoint_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.setpoint_spin, "Target temperature for PID control.")
        self.setpoint_var.trace_add('write', lambda *args: self._reset_save_on_setpoint_flag())

        # Row 2: PID Gains (Kp, Ki, Kd)
        gains_frame = ttk.Frame(self, style='Content.TFrame')
        gains_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=5) # Span 2 columns

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
        for i in range(6): gains_frame.columnconfigure(i, weight=1, uniform="gains") # Distribute space in gains frame

        # Row 4: Update PID Button
        self.update_pid_btn = ttk.Button(self, text="Update PID Params", command=self.update_pid)
        self.update_pid_btn.grid(row=2, column=0, columnspan=2, padx=5, pady=(10,5), sticky='ew') # Span 2 columns
        Tooltip(self.update_pid_btn, "Apply the current PID parameters (Setpoint, Kp, Ki, Kd).")

        # Start/Stop buttons
        self.start_pid_btn = ttk.Button(self, text="Start PID", command=self._start_pid)
        self.start_pid_btn.grid(row=3, column=0, padx=5, pady=5, sticky='ew')
        self.stop_pid_btn = ttk.Button(self, text="Stop PID", command=self._stop_pid)
        self.stop_pid_btn.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

    def update_pid(self):
        try:
            self.pid.update_tunings(self.kp_var.get(), self.ki_var.get(), self.kd_var.get())
            self.pid.update_setpoint(self.setpoint_var.get())
            self.set_status("PID parameters updated.")
        except tk.TclError as e:
            self.set_status(f"PID Update Error: Invalid value. {e}")
        except Exception as e:
            self.set_status(f"PID Update Error: {e}")

    def _start_pid(self):
        # Start PID logic here (e.g., resume PID, update UI)
        if self.on_start:
            self.on_start()
        self.set_status("PID started.")

    def _stop_pid(self):
        # Stop PID logic here (e.g., pause PID, update UI)
        if self.on_stop:
            self.on_stop()
        self.set_status("PID stopped.")

    def _reset_save_on_setpoint_flag(self):
        self._save_on_setpoint_triggered = False 