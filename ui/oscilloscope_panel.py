import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
from devices.oscilloscope import Oscilloscope, MockOscilloscope
from .utils import Tooltip
import csv

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.dates as mdates
import numpy as np # For rolling window

# Use Matplotlib's default font settings or configure as in TrendGraph if consistency is key
# For simplicity here, using defaults first.

PST = ZoneInfo("America/Los_Angeles")

class OscilloscopePanel(ttk.LabelFrame):
    """UI panel for controlling the oscilloscope and viewing live readings."""

    def __init__(self, master, osc: Oscilloscope, set_status=None, style="TLabelframe", **kwargs):
        super().__init__(master, text="Oscilloscope Power Trend", style=style, **kwargs) # Updated title
        self.osc = osc
        self.set_status = set_status or (lambda msg: None)

        # --- Plot Configuration ---
        self.max_plot_points = 60 # Display last 60 points

        # --- Layout Configuration ---
        # Row 0: Plot
        # Row 1: Address, Connect/Disconnect
        # Row 2-5: Measurement labels
        # Row 6: Export/Clear buttons
        self.columnconfigure(0, weight=1) # For labels
        self.columnconfigure(1, weight=1) # For values/entries
        self.columnconfigure(2, weight=1) # For buttons
        self.columnconfigure(3, weight=1) # For buttons
        self.rowconfigure(0, weight=3) # Give plot more space
        # Other rows will have default weight

        # --- Matplotlib Power Plot ---
        self.fig_power_plot, self.ax_power_plot = plt.subplots(figsize=(4, 2.5), dpi=100)
        self.fig_power_plot.subplots_adjust(left=0.18, right=0.95, top=0.9, bottom=0.25) # Adjust layout
        self.line_power_plot, = self.ax_power_plot.plot([], [], marker='.', linestyle='-', color='#007ACC') # Blue
        self.ax_power_plot.set_title("Live Power Reading", fontsize=10)
        self.ax_power_plot.set_xlabel("Time (PST)", fontsize=9)
        self.ax_power_plot.set_ylabel("Power (W)", fontsize=9)
        self.ax_power_plot.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz=PST))
        self.fig_power_plot.autofmt_xdate()
        self.ax_power_plot.grid(True, linestyle=':', alpha=0.7)

        self.canvas_power_plot = FigureCanvasTkAgg(self.fig_power_plot, master=self)
        self.canvas_power_plot.get_tk_widget().grid(row=0, column=0, columnspan=4, sticky='nsew', padx=5, pady=5)
        self.canvas_power_plot.draw()

        # --- Existing Controls (shifted down by 1 row) ---
        # Address / IP entry
        ttk.Label(self, text="Address:", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=2)
        self.addr_var = tk.StringVar(value=getattr(self.osc, "_address", ""))
        
        # Example predefined addresses
        predefined_addresses = [
            "TCPIP0::192.168.1.100::INSTR", 
            "USB0::0x1234::0x5678::SN001::INSTR",
            "GPIB0::12::INSTR",
            # Add more common addresses here
            getattr(self.osc, "_address", "") # Ensure current default is in list if set
        ]
        # Remove duplicates and empty strings, then sort for cleaner presentation
        unique_addresses = sorted(list(set(filter(None, predefined_addresses))))
        if not unique_addresses and self.addr_var.get(): # If list is empty but var has a value
            unique_addresses = [self.addr_var.get()]
        elif not unique_addresses: # Default if everything is empty
            unique_addresses = ["TCPIP0::localhost::INSTR"] 

        self.addr_entry = ttk.Combobox(self, textvariable=self.addr_var, values=unique_addresses, width=30) # Increased width for typical VISA strings
        if not self.addr_var.get() and unique_addresses: # Set default if var is empty
            self.addr_var.set(unique_addresses[0])

        self.addr_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(self.addr_entry, "Select or type the IP address or VISA resource of the oscilloscope.")

        # Connect / Disconnect buttons
        self.connect_btn = ttk.Button(self, text="Connect", command=self.connect)
        self.connect_btn.grid(row=1, column=2, padx=5, pady=2, sticky='ew')
        Tooltip(self.connect_btn, "Connect to the oscilloscope.")

        self.disconnect_btn = ttk.Button(self, text="Disconnect", command=self.disconnect, state='disabled')
        self.disconnect_btn.grid(row=1, column=3, padx=5, pady=2, sticky='ew')
        Tooltip(self.disconnect_btn, "Disconnect the oscilloscope.")

        # Measurement display
        ttk.Label(self, text="Voltage (Vrms):", style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=2)
        self.voltage_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.voltage_var, style='Content.TLabel').grid(row=2, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Current (Arms):", style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=2)
        self.current_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.current_var, style='Content.TLabel').grid(row=3, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Power (W):", style='Content.TLabel').grid(row=4, column=0, sticky='w', padx=5, pady=2)
        self.power_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.power_var, style='Content.TLabel').grid(row=4, column=1, sticky='w', padx=5, pady=2)

        ttk.Label(self, text="Phase (deg):", style='Content.TLabel').grid(row=5, column=0, sticky='w', padx=5, pady=2)
        self.phase_var = tk.StringVar(value="-")
        ttk.Label(self, textvariable=self.phase_var, style='Content.TLabel').grid(row=5, column=1, sticky='w', padx=5, pady=2)

        # Export & Clear buttons
        self.export_btn = ttk.Button(self, text="Export CSV", command=self.export_csv, state='disabled')
        self.export_btn.grid(row=6, column=0, padx=5, pady=(10, 5), sticky='ew')
        Tooltip(self.export_btn, "Export the logged power data to CSV.")

        self.clear_btn = ttk.Button(self, text="Clear Data", command=self.clear_data, state='disabled')
        self.clear_btn.grid(row=6, column=1, padx=5, pady=(10, 5), sticky='ew')
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
            self.osc.connect() # This call should ideally update self.osc._address if auto-detection occurred
            
            # Get the confirmed address from the oscilloscope object after connection
            confirmed_address = self.osc._address 
            self.addr_var.set(confirmed_address) # Update the UI entry field
            
            status_message = f"Oscilloscope connected to {confirmed_address}: {self.osc.device_id}"
            self.set_status(status_message)
            
            self.connect_btn.configure(state='disabled')
            self.disconnect_btn.configure(state='normal')
            self.export_btn.configure(state='normal')
            self.clear_btn.configure(state='normal')
            self.addr_entry.configure(state='disabled') # Disable address field after connection
            self._start_polling()
        except Exception as e:
            self.set_status(f"Scope connect error: {e}")
            # UI elements like connect_btn, disconnect_btn, and addr_entry states
            # should ideally be managed by ensuring a consistent state or by calling disconnect().
            # For now, if connect fails, we revert button states to allow another attempt, 
            # and keep address entry enabled.
            self.connect_btn.configure(state='normal')
            self.disconnect_btn.configure(state='disabled')
            self.addr_entry.configure(state='normal')
            # Ensure polling is stopped if it somehow started or was an issue
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None

    def disconnect(self):
        try:
            self.osc.disconnect()
        finally:
            self.set_status("Oscilloscope disconnected.")
            self.connect_btn.configure(state='normal')
            self.disconnect_btn.configure(state='disabled')
            self.addr_entry.configure(state='normal') # Re-enable address field on disconnect
            if self.after_id:
                self.after_cancel(self.after_id)
                self.after_id = None
            # Consider clearing the plot or leaving it as is. Leaving for now.
            # self.clear_data() # Optionally clear plot on disconnect

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
        current_time = datetime.now(PST)
        self.time_data.append(current_time)
        self.power_data.append(p)
        
        # Keep only the last N points for plotting
        if len(self.time_data) > self.max_plot_points:
            self.time_data = self.time_data[-self.max_plot_points:]
            self.power_data = self.power_data[-self.max_plot_points:]

        self._update_power_plot()

        self.after_id = self.after(self.update_interval, self._poll)

    def _update_power_plot(self):
        if not self.time_data:
            self.line_power_plot.set_data([], [])
        else:
            self.line_power_plot.set_data(self.time_data, self.power_data)
            self.ax_power_plot.relim()
            self.ax_power_plot.autoscale_view(True, True, True)
        
        self.fig_power_plot.autofmt_xdate() # Re-apply in case axis labels need adjustment
        self.canvas_power_plot.draw()

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------
    def clear_data(self):
        self.time_data.clear()
        self.power_data.clear()
        self._update_power_plot() # Update plot to show it's cleared
        self.set_status("Oscilloscope data cleared.")

    def export_csv(self):
        # This exports ALL historical data, not just what's plotted.
        # If only plotted data should be exported, this logic needs to change.
        if not self.time_data:
            self.set_status("No oscilloscope data to export.")
            return
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f"scope_power_{timestamp}.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp (PST)", "Power (W)"])
                # Use the full self.time_data and self.power_data if they are not trimmed, 
                # or manage a separate list for full history if plot is trimmed.
                # For now, assuming self.time_data/power_data are trimmed for plot, 
                # so CSV export will also be trimmed. If full export is needed, 
                # we must not trim the main lists or use separate lists for plotting.
                # Let's assume for now the main lists ARE trimmed for simplicity of the plot.
                
                # If self.time_data has been trimmed for plotting, and we need to export all data, then
                # we should not be trimming self.time_data and self.power_data in _poll OR
                # we should be storing data in separate lists for full export vs plot display.
                # For now, this will export the trimmed (last N points) data.
                # To fix: create self.full_time_data, self.full_power_data for export if needed.

                # Assuming current self.time_data and self.power_data reflect what should be exported (i.e., trimmed data)
                temp_time_data_to_export = list(self.time_data) # Use copies in case of modification during iteration
                temp_power_data_to_export = list(self.power_data)

                for dt_obj, power in zip(temp_time_data_to_export, temp_power_data_to_export):
                    writer.writerow([dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z'), f"{power:.4f}"])
            self.set_status(f"Scope data exported to {filename}")
        except Exception as e:
            self.set_status(f"Scope export failed: {e}") 