import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use('Agg') # Keep Agg for safety, FigureCanvasTkAgg handles Tk embedding
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import time
import csv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+
import matplotlib.dates as mdates
from .utils import Tooltip # Import the shared Tooltip
import config
# import os # os was imported but not used

# Default font for matplotlib to match app style
MPL_FONT_FAMILY = 'Segoe UI'
matplotlib.rcParams['font.family'] = MPL_FONT_FAMILY
matplotlib.rcParams['font.size'] = 9
matplotlib.rcParams['axes.titlesize'] = 11
matplotlib.rcParams['axes.labelsize'] = 10
matplotlib.rcParams['xtick.labelsize'] = 9
matplotlib.rcParams['ytick.labelsize'] = 9
matplotlib.rcParams['legend.fontsize'] = 9

# Define a second y-axis for voltage
VOLTAGE_COLOR = '#FF8F00'  # Amber/Orange for voltage

class TrendGraph(ttk.Frame):
    def __init__(self, master, set_status=None, style='Content.TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.set_status = set_status or (lambda msg: None)
        
        try:
            self.PST = ZoneInfo("America/Los_Angeles")
        except Exception as e:
            # Fallback or error handling if zoneinfo is not available or invalid timezone
            print(f"Error initializing timezone: {e}. Using UTC as fallback.")
            self.PST = ZoneInfo("UTC")
            self.set_status("Warning: Could not load PST. Using UTC for timestamps.")

        plt.style.use('seaborn-v0_8-whitegrid')

        self.fig, self.ax = plt.subplots(figsize=(5,3), dpi=100) # figsize is relative, dpi matters for Tk sizing
        self.line_max, = self.ax.plot([], [], color='#E53935', linestyle='-', linewidth=1.5, label='Max Temp') # Red
        self.line_min, = self.ax.plot([], [], color='#1E88E5', linestyle='-', linewidth=1.5, label='Min Temp') # Blue
        self.line_avg, = self.ax.plot([], [], color='#43A047', linestyle='--', linewidth=1.5, label='Avg Temp') # Green
        
        self.ax.set_ylabel('Temperature (°C)')
        self.ax.set_xlabel('Time (PST)') # Updated X-axis label
        
        # Create a second y-axis for voltage
        self.ax2 = self.ax.twinx()
        self.line_voltage, = self.ax2.plot([], [], color=VOLTAGE_COLOR, linestyle='-.', linewidth=1.5, label='Voltage (V)') # Amber/Orange
        self.ax2.set_ylabel('Voltage (V)', color=VOLTAGE_COLOR)
        self.ax2.tick_params(axis='y', labelcolor=VOLTAGE_COLOR)

        # Combine legends from both axes
        lines, labels = self.ax.get_legend_handles_labels()
        lines2, labels2 = self.ax2.get_legend_handles_labels()
        self.ax.legend(lines + lines2, labels + labels2, loc='upper left')
        
        self.ax.grid(True, linestyle=':', alpha=0.7) # Grid for primary axis
        # self.ax2.grid(False) # No separate grid for voltage axis, or style if needed
        self.fig.tight_layout(pad=0.5) # Adjust layout to prevent overlap

        # Frame for canvas and toolbar
        plot_frame = ttk.Frame(self, style='Content.TFrame')
        plot_frame.pack(side='top', fill='both', expand=True)

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(side='top', fill='both', expand=True, padx=5, pady=5)
        self.canvas.draw()

        # --- Controls for the graph ---
        controls_frame = ttk.Frame(self, style='Content.TFrame', padding=(5,5))
        controls_frame.pack(side='bottom', fill='x', expand=False)
        controls_frame.columnconfigure(0, weight=1) # Timespan combobox
        controls_frame.columnconfigure(1, weight=0) # Export button
        controls_frame.columnconfigure(2, weight=0) # Clear button

        # Time span selection
        ttk.Label(controls_frame, text="Time Window:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(5,0))
        self.time_span_options = {"30 Seconds": 30, "1 Minute": 60, "5 Minutes": 300, "10 Minutes": 600, "All Data": -1}
        self.time_span_var = tk.StringVar(value=config.TREND_GRAPH_DEFAULT_SPAN)
        self.time_span_selector = ttk.Combobox(controls_frame, textvariable=self.time_span_var, 
                                               values=list(self.time_span_options.keys()), state="readonly", width=12)
        self.time_span_selector.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        self.time_span_selector.bind("<<ComboboxSelected>>", self.on_timespan_change)
        Tooltip(self.time_span_selector, "Select the time window for the trend graph.")

        # Export and Clear buttons
        self.export_btn = ttk.Button(controls_frame, text="Export CSV", command=self.export_csv, width=12)
        self.export_btn.grid(row=0, column=2, padx=5, pady=5, sticky='e')
        Tooltip(self.export_btn, "Export all collected trend data to a CSV file.")

        self.clear_data_btn = ttk.Button(controls_frame, text="Clear Data", command=self.clear_data, width=12)
        self.clear_data_btn.grid(row=0, column=3, padx=5, pady=5, sticky='e')
        Tooltip(self.clear_data_btn, "Clear all data from the trend graph.")
        
        # Matplotlib Navigation Toolbar
        toolbar_frame = ttk.Frame(controls_frame, style='Content.TFrame')
        toolbar_frame.grid(row=1, column=0, columnspan=4, sticky='ew', pady=(0,5))
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        self.toolbar.update()
        # Remove unnecessary elements from toolbar if desired, or restyle them
        # Example: remove message label from toolbar to save space
        for child in self.toolbar.winfo_children():
            if isinstance(child, tk.Label): # This is a bit fragile, depends on internal toolbar structure
                child.pack_forget()
                break

        self.time_data = [] # Will store datetime objects
        self.max_data = []
        self.min_data = []
        self.avg_data = []
        self.voltage_data = [] # New list for voltage
        # self.start_time = time.time() # Removed, using absolute datetime objects
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_interval = config.TREND_GRAPH_UPDATE_MS  # ms; configurable

        # Configure X-axis to display time formatted in PST
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz=self.PST))
        self.fig.autofmt_xdate() # Rotate date labels for better fit

        self.after_id = self.after(self.update_interval, self.update_graph)

    def on_timespan_change(self, event=None):
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_graph() # Redraw with new span

    def add_point(self, max_temp, min_temp, avg_temp, voltage): # Added voltage parameter
        # t = time.time() - self.start_time # Removed
        self.time_data.append(datetime.now(self.PST)) # Store current PST datetime
        self.max_data.append(max_temp)
        self.min_data.append(min_temp)
        self.avg_data.append(avg_temp)
        self.voltage_data.append(voltage) # Store voltage

    def update_graph(self):
        if not self.winfo_exists(): # Don't update if widget is destroyed
            return
            
        t_now_pst = datetime.now(self.PST)

        if self.current_time_span_seconds == -1: # All Data
            plot_times = list(self.time_data) # Use a copy
            plot_max = list(self.max_data)
            plot_min = list(self.min_data)
            plot_avg = list(self.avg_data)
            plot_voltage = list(self.voltage_data)
        else:
            display_window_start_time = t_now_pst - timedelta(seconds=self.current_time_span_seconds)
            
            first_idx = 0
            # Find the first data point that is within the current display window
            # This loop ensures we only plot data that should be visible
            for i, dt in enumerate(self.time_data):
                if dt >= display_window_start_time:
                    first_idx = i
                    break
            else: # If all data is older than the display window start
                first_idx = len(self.time_data) # Results in empty plot_lists if all data is too old
            
            plot_times = self.time_data[first_idx:]
            plot_max = self.max_data[first_idx:]
            plot_min = self.min_data[first_idx:]
            plot_avg = self.avg_data[first_idx:]
            plot_voltage = self.voltage_data[first_idx:]

        self.line_max.set_data(plot_times, plot_max)
        self.line_min.set_data(plot_times, plot_min)
        self.line_avg.set_data(plot_times, plot_avg)
        self.line_voltage.set_data(plot_times, plot_voltage) # Set voltage data
        
        self.ax.relim()
        self.ax.autoscale_view()
        self.ax2.relim() # Relimit and autoscale the second axis
        self.ax2.autoscale_view()
        
        # Adjust x-axis limits for a smooth scrolling effect or fixed window
        if plot_times:
            if self.current_time_span_seconds != -1: # Scrolling window with data
                x_min_dt = t_now_pst - timedelta(seconds=self.current_time_span_seconds)
                # Add a small amount of future time to the x-axis for smoother scrolling appearance
                future_buffer_seconds = max(self.update_interval / 1000.0 * 2, 0.05 * self.current_time_span_seconds)
                x_max_dt = t_now_pst + timedelta(seconds=future_buffer_seconds)
                self.ax.set_xlim(x_min_dt, x_max_dt)
            else: # All data - autoscale handles it, but relim/autoscale_view already called.
                  # If specifically "All Data" and plot_times is not empty, autoscale is fine.
                  # self.ax.autoscale_view(True, True, True) # Ensure X is autoscaled
                  pass # autoscale_view earlier should handle this for 'All Data' with points
        else: # No data to plot, set a default window based on current time and span
            display_span_seconds = self.current_time_span_seconds if self.current_time_span_seconds != -1 else 60
            # Show a window ending slightly after 'now'
            future_buffer_seconds_empty = self.update_interval / 1000.0 * 5 # A few update intervals
            x_max_dt = t_now_pst + timedelta(seconds=future_buffer_seconds_empty)
            x_min_dt = x_max_dt - timedelta(seconds=display_span_seconds)
            self.ax.set_xlim(x_min_dt, x_max_dt)

        self.fig.autofmt_xdate() # Ensure date labels are well-formatted
        self.canvas.draw()
        self.after_id = self.after(self.update_interval, self.update_graph)

    def clear_data(self):
        self.time_data.clear()
        self.max_data.clear()
        self.min_data.clear()
        self.avg_data.clear()
        self.voltage_data.clear() # Clear voltage data
        # self.start_time = time.time() # Removed
        self.update_graph() # Redraw empty graph, which will now set axes based on current time
        self.set_status("Trend graph data cleared.")

    def export_csv(self, sample_name: str | None = None, output_path: str | None = None):
        if not self.time_data:
            self.set_status("No data to export.")
            return
        
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        
        if sample_name and sample_name.strip():
            s_name = sample_name.strip().replace(" ", "_") # Sanitize for filename
            filename = f"{s_name}_trend_{timestamp}.csv"
        else:
            filename = f"trend_{timestamp}.csv"

        # If output_path is provided, use it; otherwise, use filename in cwd
        if output_path:
            csv_path = output_path
        else:
            csv_path = filename

        try:
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp (PST)', 'Max Temp (C)', 'Min Temp (C)', 'Avg Temp (C)', 'Voltage (V)']) # Updated header
                for dt_obj, mx, mn, av, v in zip(self.time_data, self.max_data, self.min_data, self.avg_data, self.voltage_data):
                    # Format datetime object to string including PST
                    timestamp_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z')
                    writer.writerow([timestamp_str, mx, mn, av, v]) # Write formatted timestamp
            self.set_status(f"Graph data exported to {csv_path}")
        except Exception as e:
            self.set_status(f"Export failed: {e}")

    def stop(self):
        if self.after_id:
            self.after_cancel(self.after_id)