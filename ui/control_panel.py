import tkinter as tk
from tkinter import ttk
from .utils import Tooltip
import sys
import os
import serial.tools.list_ports
import config
import time
import logging
from datetime import timedelta
import requests

logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # This gets the root of the project if ui is a subdir
sys.path.insert(0, parent_dir)
from devices.camera_manager import CameraManager
from devices.data_aggregator import DataAggregator

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

def send_slack_update(message):
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        if response.status_code != 200:
            print(f"Failed to send Slack message: {response.text}")
    except Exception as e:
        print(f"Slack notification error: {e}")

class ControlPanel(ttk.LabelFrame):
    def __init__(self, master, pid, siggen, camera_manager: CameraManager, data_aggregator: DataAggregator, set_status=None, style='TLabelframe', max_voltage_var=None, status_broadcaster=None, sample_number_var=None, **kwargs):
        super().__init__(master, text="PID & Signal Generator Control", style=style, **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.camera_manager = camera_manager
        self.data_aggregator = data_aggregator
        self.set_status = set_status or (lambda msg: None)
        self.status_broadcaster = status_broadcaster
        self.columnconfigure(0, weight=1) # Make the main frame responsive
        self.max_voltage_var = max_voltage_var
        self._save_on_setpoint_triggered = False

        self.sample_number_var = sample_number_var

        # Store available cameras for mapping display names to indices
        self._available_cameras_map = {}

        self.slack_message_buffer = []

        self._cooling_100c_notified = False  # Track if 100C notification sent

        # --- Sample Name Entry (Normal View) ---
        self.sample_name_frame = ttk.Frame(self, style='Content.TFrame')
        self.sample_name_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=(0, 0))
        self.sample_name_frame.columnconfigure(1, weight=1)
        ttk.Label(self.sample_name_frame, text="Sample #:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 5), pady=5)
        self.sample_name_entry = ttk.Entry(self.sample_name_frame, textvariable=self.sample_number_var, width=20)
        self.sample_name_entry.grid(row=0, column=1, sticky='ew', padx=(0, 5), pady=5)
        Tooltip(self.sample_name_entry, "Identifier for the current sample/test run (used in snapshot filenames).")

        # --- PID Parameters Section ---
        pid_params_frame = ttk.LabelFrame(self, text="PID Parameters", style='TLabelframe', padding=(5,5))
        pid_params_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        pid_params_frame.columnconfigure(1, weight=1) # Give spinbox column more weight

        # Row 0: Setpoint
        ttk.Label(pid_params_frame, text="Setpoint (°C):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.setpoint_var = tk.DoubleVar(value=pid.setpoint)
        self.setpoint_spin = ttk.Spinbox(pid_params_frame, from_=0, to=200, increment=0.5, textvariable=self.setpoint_var, width=8)
        self.setpoint_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.setpoint_spin, "Target temperature for PID control.")
        self.setpoint_var.trace_add('write', lambda *args: self._reset_save_on_setpoint_flag())

        # Row 1: Test Strategy
        ttk.Label(pid_params_frame, text="Test Strategy:", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.test_strategy_var = tk.StringVar(value=config.DEFAULT_TEST_STRATEGY)
        self.TEST_STRATEGIES = ['Temperature Set Point', 'Voltage Step-Up to Set Point', 'Water Boil to Set Point']
        self.test_strategy_combo = ttk.Combobox(pid_params_frame, textvariable=self.test_strategy_var, values=self.TEST_STRATEGIES, state='readonly', width=25)
        self.test_strategy_combo.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.test_strategy_combo, "Select the test strategy for PID control.")
        self.test_strategy_combo.bind('<<ComboboxSelected>>', self._on_test_strategy_change)

        # Row 2: PID Gains (Kp, Ki, Kd)
        gains_frame = ttk.Frame(pid_params_frame, style='Content.TFrame')
        gains_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=5) # Span 2 columns

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

        # --- Voltage Step-Up Parameters (hidden unless needed) ---
        self.vsu_params_frame = ttk.Frame(pid_params_frame, style='Content.TFrame')
        # Initial Voltage
        ttk.Label(self.vsu_params_frame, text="Initial Voltage (V):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.vsu_initial_voltage_var = tk.DoubleVar(value=config.VSU_INITIAL_VOLTAGE)
        self.vsu_initial_voltage_spin = ttk.Spinbox(self.vsu_params_frame, from_=0, to=10, increment=0.1, textvariable=self.vsu_initial_voltage_var, width=7)
        self.vsu_initial_voltage_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_initial_voltage_spin, "Starting voltage for the step-up test.")
        # Step Size
        ttk.Label(self.vsu_params_frame, text="Step Size (V):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.vsu_step_size_var = tk.DoubleVar(value=config.VSU_STEP_SIZE)
        self.vsu_step_size_spin = ttk.Spinbox(self.vsu_params_frame, from_=0.1, to=5, increment=0.1, textvariable=self.vsu_step_size_var, width=7)
        self.vsu_step_size_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_step_size_spin, "Voltage increment for each step.")
        # Stabilization Window
        ttk.Label(self.vsu_params_frame, text="Stabilization Window (s):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.vsu_stab_window_var = tk.DoubleVar(value=config.VSU_STAB_WINDOW)
        self.vsu_stab_window_spin = ttk.Spinbox(self.vsu_params_frame, from_=1, to=60, increment=0.5, textvariable=self.vsu_stab_window_var, width=7)
        self.vsu_stab_window_spin.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_stab_window_spin, "How many seconds of stable temperature are required before stepping up.")
        # Stabilization Threshold
        ttk.Label(self.vsu_params_frame, text="Stabilization Threshold (°C):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.vsu_stab_thresh_var = tk.DoubleVar(value=config.VSU_STAB_THRESHOLD)
        self.vsu_stab_thresh_spin = ttk.Spinbox(self.vsu_params_frame, from_=0.01, to=2, increment=0.01, textvariable=self.vsu_stab_thresh_var, width=7)
        self.vsu_stab_thresh_spin.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_stab_thresh_spin, "Max allowed temperature fluctuation (°C) to consider stable.")

        # Place the frame but hide by default (now row 3)
        self.vsu_params_frame.grid(row=3, column=0, columnspan=2, sticky='ew', padx=5, pady=(0,5))
        self.vsu_params_frame.grid_remove()

        # Row 4: Update PID Button (directly in params frame)
        self.update_pid_btn = ttk.Button(pid_params_frame, text="Update PID Params", command=self.update_pid)
        self.update_pid_btn.grid(row=4, column=0, columnspan=2, padx=5, pady=(10,5), sticky='ew') # Span 2 columns
        Tooltip(self.update_pid_btn, "Apply the current PID parameters (Setpoint, Kp, Ki, Kd).")

        # Row 5: Save on setpoint checkbox
        self.save_on_setpoint_var = tk.BooleanVar(value=getattr(config, 'SAVE_ON_SETPOINT_DEFAULT', True))
        self.save_on_setpoint_chk = ttk.Checkbutton(pid_params_frame, text="Save all data when setpoint is reached", variable=self.save_on_setpoint_var, style='TCheckbutton')
        self.save_on_setpoint_chk.grid(row=5, column=0, columnspan=2, sticky='w', padx=5, pady=5)

        # --- Water Boil Parameters (hidden unless needed) ---
        self.water_boil_params_frame = ttk.Frame(pid_params_frame, style='Content.TFrame')
        # Boil Point
        ttk.Label(self.water_boil_params_frame, text="Boil Point (°C):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_point_var = tk.DoubleVar(value=config.WATER_BOIL_POINT)
        self.water_boil_point_spin = ttk.Spinbox(self.water_boil_params_frame, from_=50, to=200, increment=0.5, textvariable=self.water_boil_point_var, width=8)
        self.water_boil_point_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_point_spin, "Temperature to boil off water before main setpoint.")
        # Dwell Time
        ttk.Label(self.water_boil_params_frame, text="Boil Dwell (s):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_dwell_var = tk.DoubleVar(value=config.WATER_BOIL_DWELL)
        self.water_boil_dwell_spin = ttk.Spinbox(self.water_boil_params_frame, from_=1, to=600, increment=1, textvariable=self.water_boil_dwell_var, width=8)
        self.water_boil_dwell_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_dwell_spin, "How long to hold at boil point before moving to setpoint.")
        # Stabilization Window
        ttk.Label(self.water_boil_params_frame, text="Stabilization Window (s):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_stab_window_var = tk.DoubleVar(value=config.VSU_STAB_WINDOW)
        self.water_boil_stab_window_spin = ttk.Spinbox(self.water_boil_params_frame, from_=1, to=60, increment=0.5, textvariable=self.water_boil_stab_window_var, width=8)
        self.water_boil_stab_window_spin.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_stab_window_spin, "How many seconds of stable temperature are required before starting dwell.")
        # Stabilization Threshold
        ttk.Label(self.water_boil_params_frame, text="Stabilization Threshold (°C):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_stab_thresh_var = tk.DoubleVar(value=config.VSU_STAB_THRESHOLD)
        self.water_boil_stab_thresh_spin = ttk.Spinbox(self.water_boil_params_frame, from_=0.01, to=2, increment=0.01, textvariable=self.water_boil_stab_thresh_var, width=8)
        self.water_boil_stab_thresh_spin.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_stab_thresh_spin, "Max allowed temperature fluctuation (°C) to consider stable.")
        # Place but hide by default (now row 6)
        self.water_boil_params_frame.grid(row=6, column=0, columnspan=2, sticky='ew', padx=5, pady=(0,5))
        self.water_boil_params_frame.grid_remove()

        # --- PID Input Source & Control Section ---
        pid_control_frame = ttk.LabelFrame(self, text="PID Input & Control", style='TLabelframe', padding=(5,5))
        pid_control_frame.grid(row=2, column=0, sticky='ew', padx=5, pady=(10,5)) # Grid in main panel now
        pid_control_frame.columnconfigure(1, weight=1) # Allow comboboxes/controls to expand

        # Row 0: Source Camera
        ttk.Label(pid_control_frame, text="Source Camera(s):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.pid_cam_source_var = tk.StringVar()
        self.pid_cam_source_combo = ttk.Combobox(pid_control_frame, textvariable=self.pid_cam_source_var, state='readonly', width=25)
        self.pid_cam_source_combo.grid(row=0, column=1, columnspan=3, sticky='ew', padx=5, pady=5) # Span 3 to align with buttons below
        Tooltip(self.pid_cam_source_combo, "Select camera(s) to use for PID input.")
        self.pid_cam_source_combo.bind('<<ComboboxSelected>>', self._update_pid_input_source)

        # Row 1: Aggregation Mode
        ttk.Label(pid_control_frame, text="Aggregation Mode:", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.pid_agg_mode_var = tk.StringVar()
        self.AGGREGATION_MODES = ['average_mean', 'overall_max', 'first_valid_mean']
        self.pid_agg_mode_combo = ttk.Combobox(pid_control_frame, textvariable=self.pid_agg_mode_var, values=self.AGGREGATION_MODES, state='readonly', width=25)
        self.pid_agg_mode_combo.grid(row=1, column=1, columnspan=3, sticky='ew', padx=5, pady=5) # Span 3
        Tooltip(self.pid_agg_mode_combo, "Select how data from selected camera(s) is aggregated for PID.")
        self.pid_agg_mode_combo.bind('<<ComboboxSelected>>', self._update_pid_input_source)

        # Row 2: PID Actions (Enable, Start, Stop)
        actions_control_frame = ttk.Frame(pid_control_frame, style='Content.TFrame') # Subframe for buttons
        actions_control_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=(10, 5))

        self.pid_enable_var = tk.BooleanVar(value=True)
        self.enable_pid_chk = ttk.Checkbutton(actions_control_frame, text="Enable PID", variable=self.pid_enable_var, command=self.toggle_pid_controls)
        self.enable_pid_chk.grid(row=0, column=0, padx=5, pady=2, sticky='w')
        Tooltip(self.enable_pid_chk, "Enable or disable PID control operation.")

        self.start_pid_btn = ttk.Button(actions_control_frame, text="Start PID", command=self.start_ramp, style='Start.TButton')
        self.start_pid_btn.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
        Tooltip(self.start_pid_btn, "Start PID control loop using selected source.")

        self.stop_pid_btn = ttk.Button(actions_control_frame, text="Stop PID", command=self.stop_all, style='Stop.TButton')
        self.stop_pid_btn.grid(row=0, column=2, padx=5, pady=2, sticky='ew')
        Tooltip(self.stop_pid_btn, "Stop PID control and set output to 0V.")
        # Configure columns for button distribution
        actions_control_frame.columnconfigure(0, weight=0) # Checkbox takes minimal space
        actions_control_frame.columnconfigure(1, weight=1) # Start button expands
        actions_control_frame.columnconfigure(2, weight=1) # Stop button expands

        self._populate_pid_camera_source_options()
        self._set_initial_pid_source_ui()

        # --- Signal Generator Controls Section ---
        sg_frame = ttk.LabelFrame(self, text="Signal Generator", style='TLabelframe', padding=(5,5))
        sg_frame.grid(row=3, column=0, sticky='ew', padx=5, pady=(10,5)) # Now row 3
        sg_frame.columnconfigure(tuple(range(6)), weight=1, uniform="sg_uniform") # Allow responsive columns

        # --- Get available COM ports ---
        available_ports = serial.tools.list_ports.comports()
        port_names = [port.device for port in available_ports]
        default_port = ""
        # Try to find CH340 port
        for port in available_ports:
            if "ch340" in port.description.lower():
                default_port = port.device
                break
        # Fallback logic if no CH340 found
        if not default_port:
            current_siggen_port = self.siggen._port if self.siggen._port else ""
            if current_siggen_port and current_siggen_port in port_names:
                default_port = current_siggen_port
            elif port_names:
                default_port = port_names[0] # Fallback to first available port
            # else: default_port remains "" if no ports found

        # Connection part - Modify Port Entry to Combobox
        ttk.Label(sg_frame, text="Port:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_port_var = tk.StringVar(value=default_port)
        # Replace Entry with Combobox
        self.port_combo = ttk.Combobox(sg_frame, textvariable=self.sg_port_var, values=port_names, state='readonly' if port_names else 'disabled', width=10)
        self.port_combo.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.port_combo, "Select the serial port for the signal generator.")
        # If using Combobox, consider adding a refresh button or handling dynamic changes. For now, populated at startup.

        ttk.Label(sg_frame, text="Baud:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.sg_baud_var = tk.IntVar(value=self.siggen._baud if self.siggen._baud else 9600)
        self.baud_entry = ttk.Entry(sg_frame, textvariable=self.sg_baud_var, width=10)
        self.baud_entry.grid(row=0, column=3, sticky='ew', padx=5, pady=5)
        Tooltip(self.baud_entry, "Baud rate for the signal generator serial connection.")

        self.open_serial_btn = ttk.Button(sg_frame, text="Open", command=self.open_serial)
        self.open_serial_btn.grid(row=0, column=4, padx=5, pady=5, sticky='ew')
        Tooltip(self.open_serial_btn, "Open the selected serial port.")

        self.close_serial_btn = ttk.Button(sg_frame, text="Close", command=self.close_serial, state='disabled')
        self.close_serial_btn.grid(row=0, column=5, padx=5, pady=5, sticky='ew')
        Tooltip(self.close_serial_btn, "Close the serial port.")

        # Settings part (initially disabled)
        self.sg_settings_frame = ttk.Frame(sg_frame, style='Content.TFrame')
        self.sg_settings_frame.grid(row=1, column=0, columnspan=6, sticky='ew', pady=5)
        # Adjust columnspan for Freq and Volt rows if buttons are removed
        # Original columnspan was 8 for sg_settings_frame internal grid.
        # Freq related: Label, Spin, Set Freq btn (3 columns)
        # Volt related: Label, Spin, Set Volt btn (3 columns)
        self.sg_settings_frame.columnconfigure(tuple(range(3)), weight=1, uniform="sg_settings_reduced")

        ttk.Label(self.sg_settings_frame, text="Frequency (Hz):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_freq_var = tk.DoubleVar(value=config.SG_DEFAULT_FREQ)
        self.freq_spin = ttk.Spinbox(self.sg_settings_frame, from_=0, to=1000000, increment=100, textvariable=self.sg_freq_var, width=10)
        self.freq_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.freq_spin, "Set the output frequency in Hz.")
        self.set_freq_btn = ttk.Button(self.sg_settings_frame, text="Set Freq", command=self.set_frequency)
        self.set_freq_btn.grid(row=0, column=2, padx=5, pady=5, sticky='ew')
        Tooltip(self.set_freq_btn, "Apply the frequency to the signal generator.")

        ttk.Label(self.sg_settings_frame, text="Voltage (V):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.sg_voltage_var = tk.DoubleVar(value=config.SG_DEFAULT_VOLTAGE)
        self.volt_spin = ttk.Spinbox(self.sg_settings_frame, from_=0, to=10, increment=0.01, textvariable=self.sg_voltage_var, width=8)
        self.volt_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.volt_spin, "Set the output voltage in volts.")
        self.set_volt_btn = ttk.Button(self.sg_settings_frame, text="Set Volt", command=self.set_voltage)
        self.set_volt_btn.grid(row=1, column=2, padx=5, pady=5, sticky='ew')
        Tooltip(self.set_volt_btn, "Apply the voltage to the signal generator.")

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
            self.freq_spin, self.set_freq_btn,
            self.volt_spin, self.set_volt_btn,
            self.cmd_entry, self.send_cmd_btn
        ]
        self._toggle_sg_controls_enabled(False) # Initially disabled
        self.toggle_pid_controls() # Initial state based on checkbox

        # PID starts in a paused state, so disable the "Stop PID" button until
        # the user starts the loop.
        self.stop_pid_btn.configure(state='disabled')

        # ----- Timer / Phase State (UI label created by parent) -----
        self.phase_var = tk.StringVar(value="Idle")
        self._timer_after_id = None
        self._test_start_time: float | None = None
        self._cooling_start_time: float | None = None
        self._current_phase_desc = "Idle"

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
        self.stop_pid_btn.configure(state=state if enabled else 'disabled') # Stop btn also disabled if PID disabled AND PID is not currently running (might want to allow stop if running but disabled)
        # Directly configure spinboxes
        self.setpoint_spin.configure(state=state)
        self.kp_spin.configure(state=state)
        self.ki_spin.configure(state=state)
        self.kd_spin.configure(state=state)
        # Update button only makes sense if params are editable
        self.update_pid_btn.configure(state=state)
        # Input source selection should probably be always enabled?
        self.pid_cam_source_combo.configure(state='readonly') # Always readonly, state not changed here
        self.pid_agg_mode_combo.configure(state='readonly') # Always readonly, state not changed here

    def open_serial(self):
        logger.info("Opening Signal Generator on port %s at %s baud", self.siggen._port or self.sg_port_var.get(), self.siggen._baud or self.sg_baud_var.get())
        self.siggen._port = self.sg_port_var.get() # Get port from Combobox variable
        self.siggen._baud = self.sg_baud_var.get()
        if not self.siggen._port:
            self.set_sg_status("No COM port selected.")
            self.set_status("Please select a COM port.")
            return
        
        self.set_sg_status(f"Opening {self.siggen._port} at {self.siggen._baud} baud...")
        try:
            self.siggen.open()
            # Ensure the generator starts at 0 V so no unintended output is sent
            try:
                self.siggen.set_voltage(0.0)
            except Exception as ve:
                # If setting the voltage fails we still want to proceed, but notify the user
                self.set_status(f"Warning: Failed to set initial 0 V ({ve})")
            else:
                # Reflect the 0 V in the voltage spin-box so the UI stays consistent
                self.sg_voltage_var.set(0.0)

            status_msg = f"Opened {self.siggen._port} at {self.siggen._baud} baud."
            self.set_status(status_msg) # Main status
            self.set_sg_status(status_msg) # SG status
            self.open_serial_btn.configure(state='disabled')
            self.close_serial_btn.configure(state='normal')
            # Disable port/baud selection after opening
            self.port_combo.configure(state='disabled') 
            self.baud_entry.configure(state='disabled')
            self._toggle_sg_controls_enabled(True)
            logger.info("Signal Generator opened successfully on %s", self.siggen._port)
            # Log event to trend graph
            self._log_trend_graph_event("Signal Generator Opened")
        except Exception as e:
            error_msg = f"Error opening serial: {e}"
            self.set_status(error_msg) # Main status
            self.set_sg_status(error_msg) # SG status
            # Ensure sg controls remain disabled if open fails
            self._toggle_sg_controls_enabled(False)
            logger.exception("Failed to open Signal Generator serial port")

    def close_serial(self):
        logger.info("Closing Signal Generator serial port")
        self.set_sg_status("Closing serial port...")
        try:
            self.siggen.close()
            status_msg = "Serial port closed."
            self.set_status(status_msg)
            self.set_sg_status(status_msg)
            self.open_serial_btn.configure(state='normal')
            self.close_serial_btn.configure(state='disabled')
            # Re-enable port/baud selection after closing
            if self.port_combo['values']: # Only enable if there are ports to select
                self.port_combo.configure(state='readonly') 
            else:
                self.port_combo.configure(state='disabled')
            self.baud_entry.configure(state='normal')
            self._toggle_sg_controls_enabled(False)
            logger.info("Signal Generator serial port closed")
            self._log_trend_graph_event("Signal Generator Closed")
        except Exception as e:
            error_msg = f"Error closing serial: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)
            logger.exception("Error while closing Signal Generator serial port")

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
        self.update_pid()
        self._reset_save_on_setpoint_flag()
        strategy = self.test_strategy_var.get()
        logger.info("PID test started using strategy '%s' with setpoint %.2f°C", strategy, self.setpoint_var.get())
        self._current_phase_desc = "Test Started"
        if self.status_broadcaster:
            self.status_broadcaster.send_status("Test Started", "00:00:00", False, max_temp=None, cooling_down=False)
        send_slack_update(f"Test started! Sample: {self.get_sample_name()}")
        if strategy == 'Temperature Set Point':
            self.pid.resume()
            self.set_status("PID control started (Temperature Set Point mode).")
            self.start_pid_btn.configure(state='disabled')
            self.stop_pid_btn.configure(state='normal')
            self.enable_pid_chk.configure(state='disabled')
            self._log_trend_graph_event("PID Started")

            # --- Timer init ---
            self._test_start_time = time.time()
            self._cooling_start_time = None
            self._update_phase_timer("Heating", self._test_start_time)
            self._timer_after_id = self.after(1000, self._timer_tick)
        elif strategy == 'Voltage Step-Up to Set Point':
            self.set_status("Starting Voltage Step-Up to Set Point strategy...")
            self.start_pid_btn.configure(state='disabled')
            self.stop_pid_btn.configure(state='normal')
            self.enable_pid_chk.configure(state='disabled')
            self.start_voltage_stepup_strategy()
        elif strategy == 'Water Boil to Set Point':
            self.set_status("Starting Water Boil to Set Point strategy...")
            self.start_pid_btn.configure(state='disabled')
            self.stop_pid_btn.configure(state='normal')
            self.enable_pid_chk.configure(state='disabled')
            self.start_water_boil_strategy()

    def stop_all(self):
        logger.info("PID test stopped by user.")
        self.pid.pause()
        self.set_status("PID control stopped.")
        self.start_pid_btn.configure(state='normal')
        self.stop_pid_btn.configure(state='disabled')
        self.enable_pid_chk.configure(state='normal')
        if hasattr(self, '_vsu_running'):
            self._vsu_running = False
        if hasattr(self, '_boil_running'):
            self._boil_running = False
        self._reset_save_on_setpoint_flag()
        try:
            if self.siggen.is_open:
                self.siggen.set_voltage(0.0)
                self.set_status("PID stopped. SigGen output set to 0V.")
        except Exception as e:
            self.set_status(f"PID stopped. SigGen error: {e}")
        self._log_trend_graph_event("PID Stopped")
        if self._cooling_start_time is None:
            self._start_cooling_phase()
        if self.status_broadcaster:
            self.status_broadcaster.send_status("Cooling", "00:00:00", True, max_temp=None, cooling_down=True)
        send_slack_update(f"Test ended. Cooling phase started. Sample: {self.get_sample_name()}")

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

    def set_voltage(self):
        if not self._check_serial_open(): return
        try:
            voltage = float(self.sg_voltage_var.get())
            max_v = self.max_voltage_var.get() if self.max_voltage_var else 5.0
            if voltage > max_v:
                voltage = max_v
                self.sg_voltage_var.set(max_v)
            self.siggen.set_voltage(voltage)
            status_msg = f"Voltage set to {voltage:.2f} V (max {max_v} V)"
            self.set_sg_status(status_msg)
            # self.set_status(status_msg)
        except Exception as e:
            error_msg = f"Volt error: {e}"
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

    def _populate_pid_camera_source_options(self):
        self._available_cameras_map = {}
        camera_options = ["All Connected Cameras"] # Default option
        active_cams = self.camera_manager.get_all_cameras() if self.camera_manager else []
        
        for idx, cam in enumerate(active_cams):
            display_name = f"Camera {cam.connected_port or f'(Index {idx})'}" # Use connected_port or fallback
            camera_options.append(display_name)
            self._available_cameras_map[display_name] = idx # Map display name to original index in active_cams
            
        self.pid_cam_source_combo['values'] = camera_options
        if not active_cams:
            self.pid_cam_source_var.set("No cameras available")
            self.pid_cam_source_combo.configure(state='disabled')
        elif camera_options: # If options were populated (i.e. "All" or more)
             self.pid_cam_source_combo.configure(state='readonly')
             # Initial selection will be set by _set_initial_pid_source_ui

    def _set_initial_pid_source_ui(self):
        # Set initial aggregation mode from PID instance
        if self.pid.pid_aggregation_mode in self.AGGREGATION_MODES:
            self.pid_agg_mode_var.set(self.pid.pid_aggregation_mode)
        elif self.AGGREGATION_MODES: # Fallback to first available mode
            self.pid_agg_mode_var.set(self.AGGREGATION_MODES[0])
        
        # Set initial camera source from PID instance
        active_cams = self.camera_manager.get_all_cameras() if self.camera_manager else []
        if self.pid.pid_camera_indices is None:
            self.pid_cam_source_var.set("All Connected Cameras")
        elif self.pid.pid_camera_indices and isinstance(self.pid.pid_camera_indices, list) and len(self.pid.pid_camera_indices) == 1:
            idx_to_find = self.pid.pid_camera_indices[0]
            found_display_name = None
            for display_name, original_idx in self._available_cameras_map.items():
                if original_idx == idx_to_find:
                    found_display_name = display_name
                    break
            if found_display_name:
                self.pid_cam_source_var.set(found_display_name)
            elif self._available_cameras_map: # If specific index not found but cameras exist, default to "All"
                 self.pid_cam_source_var.set("All Connected Cameras")
            # If no cameras or map is empty, it might have been set by _populate correctly already
        elif self.pid_cam_source_combo['values']: # Default to first option if specific setup is not clear
             self.pid_cam_source_var.set(self.pid_cam_source_combo['values'][0])
        # Else, if no cameras, it's handled by _populate.

    def _update_pid_input_source(self, event=None): # event arg for bind
        if not self.data_aggregator or not self.pid: # Guard clause
            return

        selected_cam_source_str = self.pid_cam_source_var.get()
        selected_agg_mode = self.pid_agg_mode_var.get()

        camera_indices_for_pid = None # Default to None (all cameras)

        if selected_cam_source_str != "All Connected Cameras" and selected_cam_source_str in self._available_cameras_map:
            original_cam_index = self._available_cameras_map[selected_cam_source_str]
            camera_indices_for_pid = [original_cam_index]
        elif selected_cam_source_str == "No cameras available":
            # If no cameras, PID should not use aggregator or use None for indices
            # The PID.__call__ already handles None from aggregator.
             self.pid.set_input_source(self.data_aggregator, None, selected_agg_mode)
             self.set_status(f"PID Input: No cameras. Mode: {selected_agg_mode}. PID may use last known value or default.")
             return # Early exit

        # Ensure selected_agg_mode is valid
        if selected_agg_mode not in self.AGGREGATION_MODES:
            self.set_status(f"Error: Invalid PID aggregation mode selected: {selected_agg_mode}")
            # Optionally revert to a default or current PID mode
            if self.pid.pid_aggregation_mode in self.AGGREGATION_MODES:
                 self.pid_agg_mode_var.set(self.pid.pid_aggregation_mode)
            return

        try:
            self.pid.set_input_source(self.data_aggregator, camera_indices_for_pid, selected_agg_mode)
            cam_desc = "All cameras" if camera_indices_for_pid is None else f"Camera index {camera_indices_for_pid}"
            if selected_cam_source_str != "All Connected Cameras" and selected_cam_source_str in self._available_cameras_map:
                 cam_desc = selected_cam_source_str # Use the display name
            self.set_status(f"PID Input: {cam_desc}, Mode: {selected_agg_mode}")
        except Exception as e:
            error_msg = f"Error setting PID source: {e}"
            self.set_status(error_msg)
            print(error_msg) # Also print for debugging

    def start_voltage_stepup_strategy(self):
        print("[VSU] Starting voltage step-up strategy...")
        print(f"[VSU] Target temp: {self.setpoint_var.get()}, Agg mode: {self.pid_agg_mode_var.get() if hasattr(self, 'pid_agg_mode_var') else 'average_mean'}")
        print(f"[VSU] Initial voltage: {self.vsu_initial_voltage_var.get()}, Step size: {self.vsu_step_size_var.get()}, Max voltage: {self.max_voltage_var.get() if self.max_voltage_var else 'N/A'}")
        print(f"[VSU] Stab window: {self.vsu_stab_window_var.get()}s, Stab threshold: {self.vsu_stab_thresh_var.get()}°C")
        self._vsu_target_temp = self.setpoint_var.get()
        self._vsu_agg_mode = self.pid_agg_mode_var.get() if hasattr(self, 'pid_agg_mode_var') else 'average_mean'
        self._vsu_voltage = self.vsu_initial_voltage_var.get()
        self._vsu_step_size = self.vsu_step_size_var.get()
        self._vsu_max_voltage = self.max_voltage_var.get() if self.max_voltage_var else 5.0
        self._vsu_temp_buffer = []
        # Calculate buffer size from stabilization window and interval
        self._vsu_interval_ms = config.VSU_INTERVAL_MS  # ms
        stab_window_s = self.vsu_stab_window_var.get()
        self._vsu_buffer_size = max(2, int(stab_window_s * 1000 // self._vsu_interval_ms))
        self._vsu_stable_threshold = self.vsu_stab_thresh_var.get()
        self._vsu_running = True
        print(f"[VSU] Setting initial voltage: {self._vsu_voltage}")
        try:
            self.siggen.set_voltage(self._vsu_voltage)
            print(f"[VSU] Voltage set to {self._vsu_voltage}")
        except Exception as e:
            print(f"[VSU] ERROR setting voltage: {e}")
            self.set_status(f"VSU ERROR: Failed to set voltage: {e}")
            self._vsu_running = False
            return
        self.set_status(f"Voltage Step-Up: Set voltage to {self._vsu_voltage:.2f}V, waiting for stabilization...")
        self._vsu_step_loop()

    def _vsu_step_loop(self):
        print(f"[VSU] Step loop running. Running: {self._vsu_running}")
        if not self._vsu_running:
            print("[VSU] Not running, exiting step loop.")
            return
        # Get current temperature (using aggregator)
        temp = None
        if self.data_aggregator:
            temp = self.data_aggregator.get_frames_for_pid(aggregation_mode=self._vsu_agg_mode)
        print(f"[VSU] Current temp: {temp}")
        # Refresh maximum voltage in case user adjusted it in settings
        if hasattr(self, 'max_voltage_var') and self.max_voltage_var is not None:
            try:
                self._vsu_max_voltage = self.max_voltage_var.get()
            except Exception:
                pass  # Keep previous value on error
        if temp is not None:
            self._vsu_temp_buffer.append(temp)
            if len(self._vsu_temp_buffer) > self._vsu_buffer_size:
                self._vsu_temp_buffer.pop(0)
        # Check stabilization
        stabilized = False
        if len(self._vsu_temp_buffer) == self._vsu_buffer_size:
            tmax = max(self._vsu_temp_buffer)
            tmin = min(self._vsu_temp_buffer)
            print(f"[VSU] Buffer full. tmax: {tmax}, tmin: {tmin}, delta: {abs(tmax-tmin)}")
            if abs(tmax - tmin) < self._vsu_stable_threshold:
                stabilized = True
                print("[VSU] Temperature stabilized.")
        # Check if setpoint reached
        if temp is not None and temp >= self._vsu_target_temp:
            print(f"[VSU] Setpoint reached: {temp} >= {self._vsu_target_temp}")
            self._trigger_save_all_data_if_requested()
            self.set_status(f"Setpoint reached ({temp:.2f}°C). Switching to PID control.")
            self._vsu_running = False
            self.pid.resume()
            return
        # If stabilized but not at setpoint, step up voltage
        if stabilized:
            if self._vsu_voltage < self._vsu_max_voltage:
                self._vsu_voltage += self._vsu_step_size
                if self._vsu_voltage > self._vsu_max_voltage:
                    self._vsu_voltage = self._vsu_max_voltage
                print(f"[VSU] Stepping up voltage to {self._vsu_voltage}")
                try:
                    self.siggen.set_voltage(self._vsu_voltage)
                    print(f"[VSU] Voltage set to {self._vsu_voltage}")
                except Exception as e:
                    print(f"[VSU] ERROR setting voltage: {e}")
                    self.set_status(f"VSU ERROR: Failed to set voltage: {e}")
                    self._vsu_running = False
                    return
                self.set_status(f"Stabilized at {temp:.2f}°C. Increasing voltage to {self._vsu_voltage:.2f}V (max {self._vsu_max_voltage}V)...")
                self._vsu_temp_buffer.clear()
            else:
                print(f"[VSU] Max voltage reached ({self._vsu_max_voltage}V) but setpoint not achieved.")
                self.set_status(f"Max voltage reached ({self._vsu_max_voltage}V) but setpoint not achieved.")
                self._vsu_running = False
                return
        # Schedule next check
        print(f"[VSU] Scheduling next step in {self._vsu_interval_ms} ms.")
        self.after(self._vsu_interval_ms, self._vsu_step_loop)

    def _on_test_strategy_change(self, event=None):
        strategy = self.test_strategy_var.get()
        if strategy == 'Voltage Step-Up to Set Point':
            self.vsu_params_frame.grid()
        else:
            self.vsu_params_frame.grid_remove()
        if strategy == 'Water Boil to Set Point':
            self.water_boil_params_frame.grid()
        else:
            self.water_boil_params_frame.grid_remove()

    def _trigger_save_all_data_if_requested(self):
        if hasattr(self, 'save_on_setpoint_var') and self.save_on_setpoint_var.get() and not self._save_on_setpoint_triggered:
            print("[PID] save_on_setpoint_var is True, attempting to save all data via app...")
            app = self.master
            while app is not None and not hasattr(app, '_save_all_data'):
                app = getattr(app, 'master', None)
            if app is not None and hasattr(app, '_save_all_data'):
                app.after(0, app._save_all_data)
                self._save_on_setpoint_triggered = True
                # Stop the test and set voltage to 0 after saving
                app.after(100, self.stop_all)
                if self.status_broadcaster:
                    self.status_broadcaster.send_status("Cooling", "00:00:00", True, max_temp=None, cooling_down=True)
            else:
                print("[PID] Could not find _save_all_data method on any parent.")

    def _pid_setpoint_check(self, temp):
        # Call this from standard PID mode when setpoint is reached
        if temp is not None and temp >= self.setpoint_var.get():
            print(f"[PID] Setpoint reached: {temp} >= {self.setpoint_var.get()}")
            self._trigger_save_all_data_if_requested()

    def _reset_save_on_setpoint_flag(self):
        self._save_on_setpoint_triggered = False

    def start_water_boil_strategy(self):
        print("[WATER BOIL] Starting water boil strategy...")
        send_slack_update(f"Water boil phase started. Sample: {self.get_sample_name()}")
        self._boil_point = self.water_boil_point_var.get()
        self._boil_dwell = self.water_boil_dwell_var.get()
        self._boil_stab_window = self.water_boil_stab_window_var.get()
        self._boil_stab_thresh = self.water_boil_stab_thresh_var.get()
        self._boil_interval_ms = 500  # Check every 0.5s for boil phase
        self._boil_buffer_size = max(2, int(self._boil_stab_window * 1000 // self._boil_interval_ms))
        self._boil_temp_buffer = []
        self._boil_phase = 'heatup'  # 'heatup', 'stabilize', or 'dwell'
        self._boil_running = True
        self.set_status(f"Heating to {self._boil_point}°C, then stabilize for {self._boil_stab_window}s, then dwell for {self._boil_dwell}s.")
        self._boil_start_time = None
        self.pid.update_setpoint(self._boil_point)
        self.pid.resume()
        self._water_boil_loop()

    def _water_boil_loop(self):
        if not self._boil_running:
            print("[WATER BOIL] Not running, exiting loop.")
            return
        temp = None
        # Always use the current PID aggregation mode
        agg_mode = getattr(self.pid, 'pid_aggregation_mode', 'average_mean')
        if self.data_aggregator:
            temp = self.data_aggregator.get_frames_for_pid(aggregation_mode=agg_mode)
        print(f"[WATER BOIL] Current temp: {temp}, phase: {self._boil_phase}, agg_mode: {agg_mode}")
        if self._boil_phase == 'heatup':
            if temp is not None and temp >= self._boil_point:
                print(f"[WATER BOIL] Boil point reached: {temp} >= {self._boil_point}")
                send_slack_update(f"Boil point reached at {temp:.2f}°C. Stabilizing. Sample: {self.get_sample_name()}")
                self._boil_phase = 'stabilize'
                self._boil_temp_buffer = []
                self.set_status(f"Boil point reached. Stabilizing for {self._boil_stab_window}s...")
            self.after(self._boil_interval_ms, self._water_boil_loop)
        elif self._boil_phase == 'stabilize':
            if temp is not None:
                self._boil_temp_buffer.append(temp)
                if len(self._boil_temp_buffer) > self._boil_buffer_size:
                    self._boil_temp_buffer.pop(0)
            stabilized = False
            if len(self._boil_temp_buffer) == self._boil_buffer_size:
                tmax = max(self._boil_temp_buffer)
                tmin = min(self._boil_temp_buffer)
                delta = abs(tmax - tmin)
                print(f"[WATER BOIL] Stabilization buffer full. tmax: {tmax}, tmin: {tmin}, delta: {delta}")
                if delta < self._boil_stab_thresh:
                    stabilized = True
            if stabilized:
                print("[WATER BOIL] Temperature stabilized. Starting dwell phase.")
                send_slack_update(f"Temperature stabilized at {temp:.2f}°C. Dwell phase started. Sample: {self.get_sample_name()}")
                self.set_status(f"Stabilized at {temp:.2f}°C. Dwell for {self._boil_dwell}s...")
                self._boil_phase = 'dwell'
                self._boil_start_time = time.time()
                # --- Best practices fix: Explicitly set PID setpoint and resume PID at start of dwell phase ---
                self.pid.update_setpoint(self._boil_point)
                self.pid.resume()
            else:
                remaining = self._boil_stab_window - (len(self._boil_temp_buffer) * self._boil_interval_ms / 1000)
                self.set_status(f"Stabilizing at boil point... {max(0, remaining):.1f}s left.")
            self.after(self._boil_interval_ms, self._water_boil_loop)
        elif self._boil_phase == 'dwell':
            if self._boil_start_time is None:
                self._boil_start_time = time.time()
            elapsed = time.time() - self._boil_start_time
            remaining = self._boil_dwell - elapsed
            print(f"[WATER BOIL] Dwell elapsed: {elapsed:.1f}s, remaining: {remaining:.1f}s")
            if remaining > 0:
                self.set_status(f"Boil dwell: {remaining:.1f} seconds remaining...")
                self.after(self._boil_interval_ms, self._water_boil_loop)
            else:
                print("[WATER BOIL] Dwell complete. Switching to user setpoint PID control.")
                send_slack_update(f"Boil dwell complete. Data captured and switching to user setpoint PID control. Sample: {self.get_sample_name()}")
                self.set_status("Boil dwell complete. Switching to user setpoint PID control.")
                self._boil_running = False
                self.pid.update_setpoint(self.setpoint_var.get())
                self.pid.resume()

    # ----------------- Internal helper -----------------
    def _log_trend_graph_event(self, description: str):
        """Send an event description to the TrendGraph instance if reachable."""
        parent = self.master
        while parent is not None and not hasattr(parent, 'trend_graph'):
            parent = getattr(parent, 'master', None)
        if parent is not None and hasattr(parent, 'trend_graph'):
            tg = getattr(parent, 'trend_graph')
            if tg and hasattr(tg, 'log_event'):
                try:
                    tg.log_event(description)
                except Exception:
                    pass  # Do not interrupt UI flow if logging fails

    # ---------------- Timer helpers -----------------
    def _update_phase_timer(self, phase: str, start_time: float):
        elapsed = timedelta(seconds=int(time.time() - start_time))
        self._current_phase_desc = phase
        self.phase_var.set(f"{phase}: {elapsed}")

    def _timer_tick(self):
        if self._test_start_time is not None:
            self._update_phase_timer(self._current_phase_desc, self._test_start_time)
            self._timer_after_id = self.after(1000, self._timer_tick)

    def _start_cooling_phase(self):
        self._cooling_start_time = time.time()
        self._current_phase_desc = "Cooling"
        self._update_phase_timer("Cooling", self._cooling_start_time)
        self._timer_after_id = self.after(1000, self._cooling_timer_tick)
        self._cooling_100c_notified = False  # Reset notification flag at start

    def _cooling_timer_tick(self):
        if self._cooling_start_time is not None:
            self._update_phase_timer(self._current_phase_desc, self._cooling_start_time)
            # --- Check for 100C notification ---
            temp = None
            if self.data_aggregator:
                agg_mode = getattr(self.pid, 'pid_aggregation_mode', 'average_mean')
                temp = self.data_aggregator.get_frames_for_pid(aggregation_mode=agg_mode)
            if temp is not None and not self._cooling_100c_notified and temp <= 100.0:
                send_slack_update(f"Sample has cooled to 100°C. Sample: {self.get_sample_name()}")
                self._cooling_100c_notified = True
            self._timer_after_id = self.after(1000, self._cooling_timer_tick)

    def get_sample_name(self):
        if self.sample_number_var is not None:
            return str(self.sample_number_var.get())
        return "Unknown Sample"