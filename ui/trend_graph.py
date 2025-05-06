import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use('Agg') # Keep Agg for safety, FigureCanvasTkAgg handles Tk embedding
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import time
import csv
from .utils import Tooltip # Import the shared Tooltip
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

class TrendGraph(ttk.Frame):
    def __init__(self, master, set_status=None, style='Content.TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.set_status = set_status or (lambda msg: None)

        plt.style.use('seaborn-v0_8-whitegrid')

        self.fig, self.ax = plt.subplots(figsize=(5,3), dpi=100) # figsize is relative, dpi matters for Tk sizing
        self.line_max, = self.ax.plot([], [], color='#E53935', linestyle='-', linewidth=1.5, label='Max Temp') # Red
        self.line_min, = self.ax.plot([], [], color='#1E88E5', linestyle='-', linewidth=1.5, label='Min Temp') # Blue
        self.line_avg, = self.ax.plot([], [], color='#43A047', linestyle='--', linewidth=1.5, label='Avg Temp') # Green
        
        self.ax.set_ylabel('Temperature (°C)')
        self.ax.set_xlabel('Time (s)')
        self.ax.legend(loc='upper left')
        self.ax.grid(True, linestyle=':', alpha=0.7)
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
        self.time_span_var = tk.StringVar(value="1 Minute")
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

        self.time_data = []
        self.max_data = []
        self.min_data = []
        self.avg_data = []
        self.start_time = time.time()
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_interval = 500  # ms, graph updates less frequently than heatmap
        self.after_id = self.after(self.update_interval, self.update_graph)

    def on_timespan_change(self, event=None):
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_graph() # Redraw with new span

    def add_point(self, max_temp, min_temp, avg_temp):
        t = time.time() - self.start_time
        self.time_data.append(t)
        self.max_data.append(max_temp)
        self.min_data.append(min_temp)
        self.avg_data.append(avg_temp)

    def update_graph(self):
        if not self.winfo_exists(): # Don't update if widget is destroyed
            return
            
        t_now = time.time() - self.start_time

        if self.current_time_span_seconds == -1: # All Data
            plot_times = self.time_data
            plot_max = self.max_data
            plot_min = self.min_data
            plot_avg = self.avg_data
        else:
            t_min_display = t_now - self.current_time_span_seconds
            # Filter data that falls within the current display window
            # We need to find the first index that is >= t_min_display
            first_idx = 0
            for i, ti in enumerate(self.time_data):
                if ti >= t_min_display:
                    first_idx = i
                    break
            else: # If no data is recent enough (e.g. after clearing or pausing)
                if self.time_data: # If there is old data, this means it is all too old
                    first_idx = len(self.time_data) # Will result in empty lists below
            
            plot_times = self.time_data[first_idx:]
            plot_max = self.max_data[first_idx:]
            plot_min = self.min_data[first_idx:]
            plot_avg = self.avg_data[first_idx:]

        self.line_max.set_data(plot_times, plot_max)
        self.line_min.set_data(plot_times, plot_min)
        self.line_avg.set_data(plot_times, plot_avg)
        
        self.ax.relim()
        self.ax.autoscale_view()
        
        # Adjust x-axis limits for a smooth scrolling effect if not showing all data
        if self.current_time_span_seconds != -1 and plot_times:
            self.ax.set_xlim(max(0, t_now - self.current_time_span_seconds), t_now + max(1, 0.05 * self.current_time_span_seconds)) # Small buffer
        elif not plot_times: # No data to plot
             self.ax.set_xlim(0, self.current_time_span_seconds if self.current_time_span_seconds !=-1 else 60)

        self.canvas.draw()
        self.after_id = self.after(self.update_interval, self.update_graph)

    def clear_data(self):
        self.time_data.clear()
        self.max_data.clear()
        self.min_data.clear()
        self.avg_data.clear()
        self.start_time = time.time() # Reset start time
        self.update_graph() # Redraw empty graph
        self.set_status("Trend graph data cleared.")

    def export_csv(self):
        if not self.time_data:
            self.set_status("No data to export.")
            return
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        filename = f"trend_{timestamp}.csv"
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Time (s)', 'Max Temp (C)', 'Min Temp (C)', 'Avg Temp (C)'])
                for t, mx, mn, av in zip(self.time_data, self.max_data, self.min_data, self.avg_data):
                    writer.writerow([t, mx, mn, av])
            self.set_status(f"Graph data exported to {filename}")
        except Exception as e:
            self.set_status(f"Export failed: {e}")

    def stop(self):
        if self.after_id:
            self.after_cancel(self.after_id)