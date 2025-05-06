import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
from devices.oscilloscope import Oscilloscope, MockOscilloscope
from .utils import Tooltip
import csv

PST = ZoneInfo("America/Los_Angeles")

class OscilloscopePanel(ttk.LabelFrame):
    """UI panel for controlling the oscilloscope and viewing live readings."""

    def __init__(self, master, osc: Oscilloscope, set_status=None, style="TLabelframe", **kwargs):
        super().__init__(master, text="Oscilloscope", style=style, **kwargs)
        self.osc = osc
        self.set_status = set_status or (lambda msg: None)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=1)

        # Address / IP entry
        ttk.Label(self, text="Address:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=2)
        self.addr_var = tk.StringVar(value=getattr(self.osc, "_address", ""))
        self.addr_entry = ttk.Entry(self, textvariable=self.addr_var, width=15)
        self.addr_entry.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.addr_entry, "IP address or VISA resource of the oscilloscope.")

        # Connect / Disconnect buttons
        self.connect_btn = ttk.Button(self, text="Connect", command=self.connect)
        self.connect_btn.grid(row=0, column=2, padx=5, pady=2, sticky='ew')
        Tooltip(self.connect_btn, "Connect to the oscilloscope.")

        self.disconnect_btn = ttk.Button(self, text="Disconnect", command=self.disconnect, state='disabled')
        self.disconnect_btn.grid(row=0, column=3, padx=5, pady=2, sticky='ew')
        Tooltip(self.disconnect_btn, "Disconnect the oscilloscope.")

        # Measurement display
        ttk.Label(self, text="Voltage (Vrms):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.voltage_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.voltage_var, style='Content.TLabel').grid(row=1, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Current (Arms):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.current_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.current_var, style='Content.TLabel').grid(row=2, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Power (W):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.power_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.power_var, style='Content.TLabel').grid(row=3, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Phase (deg):", style='Content.TLabel').grid(row=4, column=0, sticky='w', padx=5, pady=2)
        self.phase_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.phase_var, style='Content.TLabel').grid(row=4, column=1, sticky='w', padx=5, pady=2)

        # Export & Clear buttons
        self.export_btn = ttk.Button(self, text="Export CSV", command=self.export_csv, state='disabled')
        self.export_btn.grid(row=5, column=0, padx=5, pady=(10, 5), sticky='ew')
        Tooltip(self.export_btn, "Export the logged power data to CSV.")

        self.clear_btn = ttk.Button(self, text="Clear Data", command=self.clear_data, state='disabled')
        self.clear_btn.grid(row=5, column=1, padx=5, pady=(10, 5), sticky='ew')
        Tooltip(self.clear_btn, "Clear logged data.")

        # Internal logging arrays
        self.time_data: list[datetime] = []
        self.power_data: list[float] = []

        self.update_interval = 1000  # ms
        self.after_id = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self):
        self.osc._address = self.addr_var.get().strip()
        try:
            self.osc.connect()
            self.set_status(f"Oscilloscope connected: {self.osc.device_id}")
            self.connect_btn.configure(state='disabled')
            self.disconnect_btn.configure(state='normal')
            self.export_btn.configure(state='normal')
            self.clear_btn.configure(state='normal')
            self.addr_entry.configure(state='disabled')
            self._start_polling()
        except Exception as e:
            self.set_status(f"Scope connect error: {e}")

    def disconnect(self):
        try:
            self.osc.disconnect()
        finally:
            self.set_status("Oscilloscope disconnected.")
            self.connect_btn.configure(state='normal')
            self.disconnect_btn.configure(state='disabled')
            self.addr_entry.configure(state='normal')
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None

    # ------------------------------------------------------------------
    # Polling & display
    # ------------------------------------------------------------------
    def _start_polling(self):
        self._poll()

    def _poll(self):
        if not self.osc.is_connected:
            return
        v, i, p, ph = self.osc.get_outputs()
        self.voltage_var.set(f"{v:.2f}")
        self.current_var.set(f"{i:.3f}")
        self.power_var.set(f"{p:.3f}")
        self.phase_var.set(f"{ph:.1f}")

        # Log power
        self.time_data.append(datetime.now(PST))
        self.power_data.append(p)

        self.after_id = self.after(self.update_interval, self._poll)

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------
    def clear_data(self):
        self.time_data.clear()
        self.power_data.clear()
        self.set_status("Oscilloscope data cleared.")

    def export_csv(self):
        if not self.time_data:
            self.set_status("No oscilloscope data to export.")
            return
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f"scope_power_{timestamp}.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp (PST)", "Power (W)"])
                for dt_obj, power in zip(self.time_data, self.power_data):
                    writer.writerow([dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z'), f"{power:.4f}"])
            self.set_status(f"Scope data exported to {filename}")
        except Exception as e:
            self.set_status(f"Scope export failed: {e}") 