from .pid_controls import PIDControls
from .signal_generator_controls import SignalGeneratorControls
from .strategy_controls import StrategyControls
from .status_controls import StatusControls

import tkinter as tk
from tkinter import ttk
from ..utils import Tooltip

class ControlPanel(ttk.LabelFrame):
    """
    Orchestrator for the PID & Signal Generator Control Panel.
    Composes modular subcomponents for PID controls, signal generator controls, test strategy, and status display.
    """
    def __init__(self, master, pid, siggen, camera_manager, data_aggregator, set_status=None, style='TLabelframe', max_voltage_var=None, status_broadcaster=None, **kwargs):
        super().__init__(master, text="PID & Signal Generator Control", style=style, **kwargs)
        self.pid = pid
        self.siggen = siggen
        self.camera_manager = camera_manager
        self.data_aggregator = data_aggregator
        self.set_status = set_status or (lambda msg: None)
        self.status_broadcaster = status_broadcaster
        self.max_voltage_var = max_voltage_var

        # Compose subcomponents
        self.pid_controls = PIDControls(self, pid, set_status=self.set_status, max_voltage_var=max_voltage_var, on_start=self._on_pid_start, on_stop=self._on_pid_stop)
        self.pid_controls.grid(row=0, column=0, sticky='ew', padx=5, pady=5)

        self.strategy_controls = StrategyControls(self, pid, siggen, data_aggregator, set_status=self.set_status, max_voltage_var=max_voltage_var, on_strategy_change=self._on_strategy_change)
        self.strategy_controls.grid(row=1, column=0, sticky='ew', padx=5, pady=5)

        self.signal_generator_controls = SignalGeneratorControls(self, siggen, set_status=self.set_status, max_voltage_var=max_voltage_var, on_open=self._on_sg_open, on_close=self._on_sg_close)
        self.signal_generator_controls.grid(row=2, column=0, sticky='ew', padx=5, pady=5)

        self.status_controls = StatusControls(self)
        self.status_controls.grid(row=3, column=0, sticky='ew', padx=5, pady=5)

        self.columnconfigure(0, weight=1)

        # TODO: Wire up callbacks/events between subcomponents as needed
        # For example, propagate status updates, or trigger actions across components 

    def _on_pid_start(self):
        self.status_controls.set_phase("Heating")
        self.status_controls.set_status("PID started.")

    def _on_pid_stop(self):
        self.status_controls.set_phase("Idle")
        self.status_controls.set_status("PID stopped.")

    def _on_strategy_change(self, strategy):
        self.status_controls.set_status(f"Strategy changed to: {strategy}")

    def _on_sg_open(self):
        self.status_controls.set_status("Signal Generator serial port opened.")

    def _on_sg_close(self):
        self.status_controls.set_status("Signal Generator serial port closed.") 