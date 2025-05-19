import tkinter as tk
from tkinter import ttk
from ..utils import Tooltip
import config

class StrategyControls(ttk.LabelFrame):
    """
    UI component for test strategy selection and logic (e.g., voltage step-up, water boil).
    Handles strategy selection, voltage step-up, and water boil parameters and logic.
    """
    def __init__(self, master, pid, siggen, data_aggregator, set_status=None, style='TLabelframe', max_voltage_var=None, **kwargs):
        super().__init__(master, text="Test Strategy", style=style, **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.data_aggregator = data_aggregator
        self.set_status = set_status or (lambda msg: None)
        self.max_voltage_var = max_voltage_var
        self._save_on_setpoint_triggered = False

        # Strategy selection
        ttk.Label(self, text="Test Strategy:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.test_strategy_var = tk.StringVar(value=config.DEFAULT_TEST_STRATEGY)
        self.TEST_STRATEGIES = ['Temperature Set Point', 'Voltage Step-Up to Set Point', 'Water Boil to Set Point']
        self.test_strategy_combo = ttk.Combobox(self, textvariable=self.test_strategy_var, values=self.TEST_STRATEGIES, state='readonly', width=25)
        self.test_strategy_combo.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.test_strategy_combo, "Select the test strategy for PID control.")
        self.test_strategy_combo.bind('<<ComboboxSelected>>', self._on_test_strategy_change)

        # --- Voltage Step-Up Parameters (hidden unless needed) ---
        self.vsu_params_frame = ttk.Frame(self, style='Content.TFrame')
        ttk.Label(self.vsu_params_frame, text="Initial Voltage (V):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.vsu_initial_voltage_var = tk.DoubleVar(value=config.VSU_INITIAL_VOLTAGE)
        self.vsu_initial_voltage_spin = ttk.Spinbox(self.vsu_params_frame, from_=0, to=10, increment=0.1, textvariable=self.vsu_initial_voltage_var, width=7)
        self.vsu_initial_voltage_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_initial_voltage_spin, "Starting voltage for the step-up test.")
        ttk.Label(self.vsu_params_frame, text="Step Size (V):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.vsu_step_size_var = tk.DoubleVar(value=config.VSU_STEP_SIZE)
        self.vsu_step_size_spin = ttk.Spinbox(self.vsu_params_frame, from_=0.1, to=5, increment=0.1, textvariable=self.vsu_step_size_var, width=7)
        self.vsu_step_size_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_step_size_spin, "Voltage increment for each step.")
        ttk.Label(self.vsu_params_frame, text="Stabilization Window (s):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.vsu_stab_window_var = tk.DoubleVar(value=config.VSU_STAB_WINDOW)
        self.vsu_stab_window_spin = ttk.Spinbox(self.vsu_params_frame, from_=1, to=60, increment=0.5, textvariable=self.vsu_stab_window_var, width=7)
        self.vsu_stab_window_spin.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_stab_window_spin, "How many seconds of stable temperature are required before stepping up.")
        ttk.Label(self.vsu_params_frame, text="Stabilization Threshold (°C):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.vsu_stab_thresh_var = tk.DoubleVar(value=config.VSU_STAB_THRESHOLD)
        self.vsu_stab_thresh_spin = ttk.Spinbox(self.vsu_params_frame, from_=0.01, to=2, increment=0.01, textvariable=self.vsu_stab_thresh_var, width=7)
        self.vsu_stab_thresh_spin.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.vsu_stab_thresh_spin, "Max allowed temperature fluctuation (°C) to consider stable.")
        self.vsu_params_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=5, pady=(0,5))
        self.vsu_params_frame.grid_remove()

        # --- Water Boil Parameters (hidden unless needed) ---
        self.water_boil_params_frame = ttk.Frame(self, style='Content.TFrame')
        ttk.Label(self.water_boil_params_frame, text="Boil Point (°C):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_point_var = tk.DoubleVar(value=config.WATER_BOIL_POINT)
        self.water_boil_point_spin = ttk.Spinbox(self.water_boil_params_frame, from_=50, to=200, increment=0.5, textvariable=self.water_boil_point_var, width=8)
        self.water_boil_point_spin.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_point_spin, "Temperature to boil off water before main setpoint.")
        ttk.Label(self.water_boil_params_frame, text="Boil Dwell (s):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_dwell_var = tk.DoubleVar(value=config.WATER_BOIL_DWELL)
        self.water_boil_dwell_spin = ttk.Spinbox(self.water_boil_params_frame, from_=1, to=600, increment=1, textvariable=self.water_boil_dwell_var, width=8)
        self.water_boil_dwell_spin.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_dwell_spin, "How long to hold at boil point before moving to setpoint.")
        ttk.Label(self.water_boil_params_frame, text="Stabilization Window (s):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_stab_window_var = tk.DoubleVar(value=config.VSU_STAB_WINDOW)
        self.water_boil_stab_window_spin = ttk.Spinbox(self.water_boil_params_frame, from_=1, to=60, increment=0.5, textvariable=self.water_boil_stab_window_var, width=8)
        self.water_boil_stab_window_spin.grid(row=2, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_stab_window_spin, "How many seconds of stable temperature are required before starting dwell.")
        ttk.Label(self.water_boil_params_frame, text="Stabilization Threshold (°C):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.water_boil_stab_thresh_var = tk.DoubleVar(value=config.VSU_STAB_THRESHOLD)
        self.water_boil_stab_thresh_spin = ttk.Spinbox(self.water_boil_params_frame, from_=0.01, to=2, increment=0.01, textvariable=self.water_boil_stab_thresh_var, width=8)
        self.water_boil_stab_thresh_spin.grid(row=3, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.water_boil_stab_thresh_spin, "Max allowed temperature fluctuation (°C) to consider stable.")
        self.water_boil_params_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=5, pady=(0,5))
        self.water_boil_params_frame.grid_remove()

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