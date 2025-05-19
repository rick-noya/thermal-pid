import tkinter as tk
from tkinter import ttk
from ..utils import Tooltip
import config
import serial.tools.list_ports
import logging

logger = logging.getLogger(__name__)

class SignalGeneratorControls(ttk.LabelFrame):
    """
    UI component for signal generator controls and serial communication logic.
    Handles port selection, baud rate, frequency, voltage, raw commands, and open/close logic.
    Callbacks:
        on_open: Called after the serial port is opened.
        on_close: Called after the serial port is closed.
    """
    def __init__(self, master, siggen, set_status=None, style='TLabelframe', max_voltage_var=None, on_open=None, on_close=None, **kwargs):
        super().__init__(master, text="Signal Generator", style=style, **kwargs)
        self.siggen = siggen
        self.set_status = set_status or (lambda msg: None)
        self.max_voltage_var = max_voltage_var
        self.on_open = on_open
        self.on_close = on_close

        # --- Get available COM ports ---
        available_ports = serial.tools.list_ports.comports()
        port_names = [port.device for port in available_ports]
        default_port = ""
        for port in available_ports:
            if "ch340" in port.description.lower():
                default_port = port.device
                break
        if not default_port:
            current_siggen_port = self.siggen._port if self.siggen._port else ""
            if current_siggen_port and current_siggen_port in port_names:
                default_port = current_siggen_port
            elif port_names:
                default_port = port_names[0]

        # Port selection
        ttk.Label(self, text="Port:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_port_var = tk.StringVar(value=default_port)
        self.port_combo = ttk.Combobox(self, textvariable=self.sg_port_var, values=port_names, state='readonly' if port_names else 'disabled', width=10)
        self.port_combo.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(self.port_combo, "Select the serial port for the signal generator.")

        # Baud rate
        ttk.Label(self, text="Baud:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=5, pady=5)
        self.sg_baud_var = tk.IntVar(value=self.siggen._baud if self.siggen._baud else 9600)
        self.baud_entry = ttk.Entry(self, textvariable=self.sg_baud_var, width=10)
        self.baud_entry.grid(row=0, column=3, sticky='ew', padx=5, pady=5)
        Tooltip(self.baud_entry, "Baud rate for the signal generator serial connection.")

        # Open/Close buttons
        self.open_serial_btn = ttk.Button(self, text="Open", command=self.open_serial)
        self.open_serial_btn.grid(row=0, column=4, padx=5, pady=5, sticky='ew')
        Tooltip(self.open_serial_btn, "Open the selected serial port.")
        self.close_serial_btn = ttk.Button(self, text="Close", command=self.close_serial, state='disabled')
        self.close_serial_btn.grid(row=0, column=5, padx=5, pady=5, sticky='ew')
        Tooltip(self.close_serial_btn, "Close the serial port.")

        # Frequency and Voltage controls
        self.sg_settings_frame = ttk.Frame(self, style='Content.TFrame')
        self.sg_settings_frame.grid(row=1, column=0, columnspan=6, sticky='ew', pady=5)
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

        # Raw command
        self.sg_raw_cmd_frame = ttk.Frame(self, style='Content.TFrame')
        self.sg_raw_cmd_frame.grid(row=2, column=0, columnspan=6, sticky='ew', pady=5)
        self.sg_raw_cmd_frame.columnconfigure(1, weight=1)
        ttk.Label(self.sg_raw_cmd_frame, text="Raw Cmd:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sg_cmd_var = tk.StringVar()
        self.cmd_entry = ttk.Entry(self.sg_raw_cmd_frame, textvariable=self.sg_cmd_var, width=30)
        self.cmd_entry.grid(row=0, column=1, columnspan=2, sticky='ew', padx=5, pady=5)
        Tooltip(self.cmd_entry, "Send a raw command string to the signal generator.")
        self.send_cmd_btn = ttk.Button(self.sg_raw_cmd_frame, text="Send", command=self.send_cmd)
        self.send_cmd_btn.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        Tooltip(self.send_cmd_btn, "Send the raw command to the signal generator.")

        # Status bar
        self.sg_status_var = tk.StringVar(value="Signal Generator Ready.")
        sg_status_label = ttk.Label(self, textvariable=self.sg_status_var, style='Status.TLabel', anchor='w', relief='flat', padding=(3,2))
        sg_status_label.grid(row=3, column=0, columnspan=6, sticky='ew', padx=5, pady=(5,2))

        # Group all SG controls that should be disabled/enabled together
        self.sg_interactive_widgets = [
            self.freq_spin, self.set_freq_btn,
            self.volt_spin, self.set_volt_btn,
            self.cmd_entry, self.send_cmd_btn
        ]
        self._toggle_sg_controls_enabled(False)

    def _toggle_sg_controls_enabled(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        for widget in self.sg_interactive_widgets:
            widget.configure(state=state)

    def open_serial(self):
        logger.info("Opening Signal Generator on port %s at %s baud", self.siggen._port or self.sg_port_var.get(), self.siggen._baud or self.sg_baud_var.get())
        self.siggen._port = self.sg_port_var.get()
        self.siggen._baud = self.sg_baud_var.get()
        if not self.siggen._port:
            self.set_sg_status("No COM port selected.")
            self.set_status("Please select a COM port.")
            return
        self.set_sg_status(f"Opening {self.siggen._port} at {self.siggen._baud} baud...")
        try:
            self.siggen.open()
            try:
                self.siggen.set_voltage(0.0)
            except Exception as ve:
                self.set_status(f"Warning: Failed to set initial 0 V ({ve})")
            else:
                self.sg_voltage_var.set(0.0)
            status_msg = f"Opened {self.siggen._port} at {self.siggen._baud} baud."
            self.set_status(status_msg)
            self.set_sg_status(status_msg)
            self.open_serial_btn.configure(state='disabled')
            self.close_serial_btn.configure(state='normal')
            self.port_combo.configure(state='disabled')
            self.baud_entry.configure(state='disabled')
            self._toggle_sg_controls_enabled(True)
            logger.info("Signal Generator opened successfully on %s", self.siggen._port)
            if self.on_open:
                self.on_open()
        except Exception as e:
            error_msg = f"Error opening serial: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)
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
            if self.port_combo['values']:
                self.port_combo.configure(state='readonly')
            else:
                self.port_combo.configure(state='disabled')
            self.baud_entry.configure(state='normal')
            self._toggle_sg_controls_enabled(False)
            logger.info("Signal Generator serial port closed")
            if self.on_close:
                self.on_close()
        except Exception as e:
            error_msg = f"Error closing serial: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)
            logger.exception("Error while closing Signal Generator serial port")

    def set_frequency(self):
        if not self._check_serial_open(): return
        try:
            freq = int(self.sg_freq_var.get())
            self.siggen.set_frequency(freq)
            status_msg = f"Frequency set to {freq} Hz"
            self.set_sg_status(status_msg)
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
            self.sg_cmd_var.set("")
        except Exception as e:
            error_msg = f"Cmd '{cmd}' error: {e}"
            self.set_status(error_msg)
            self.set_sg_status(error_msg)

    def set_sg_status(self, msg):
        self.sg_status_var.set(msg)

    def _check_serial_open(self):
        if not self.siggen.is_open:
            self.set_sg_status("Serial port not open. Please open port first.")
            return False
        return True 