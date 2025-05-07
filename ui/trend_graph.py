import tkinter as tk
from tkinter import ttk
import matplotlib
# matplotlib.use('Agg') # Keep Agg for safety, FigureCanvasTkAgg handles Tk embedding
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import time
import csv
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo # Requires Python 3.9+
import matplotlib.dates as mdates
from .utils import Tooltip # Import the shared Tooltip
# import os # os was imported but not used

# --- Logging setup ---
import logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

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
CURRENT_COLOR = '#00ACC1'  # Cyan for current
POWER_COLOR = '#7E57C2'    # Deep Purple for power

class TrendGraph(ttk.Frame):
    def __init__(self, master, set_status=None, style='Content.TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.set_status = set_status or (lambda msg: None)
        
        try:
            self.PST = ZoneInfo("America/Los_Angeles")
        except Exception as e:
            logger.warning(f"Error initializing timezone: {e}. Using UTC as fallback.")
            self.PST = ZoneInfo("UTC")
            self.set_status("Warning: Could not load PST. Using UTC for timestamps.")

        plt.style.use('seaborn-v0_8-whitegrid')

        self.fig, self.ax = plt.subplots(figsize=(5,3), dpi=100) # figsize is relative, dpi matters for Tk sizing
        self.line_max, = self.ax.plot([], [], color='#E53935', linestyle='-', linewidth=1.5, label='Max Temp') # Red
        self.line_min, = self.ax.plot([], [], color='#1E88E5', linestyle='-', linewidth=1.5, label='Min Temp') # Blue
        self.line_avg, = self.ax.plot([], [], color='#43A047', linestyle='--', linewidth=1.5, label='Avg Temp') # Green
        
        self.ax.set_ylabel('Temperature (°C)')
        self.ax.set_xlabel('Time (PST)') # Updated X-axis label
        
        # Create a second y-axis for the selected quantity
        self.ax2 = self.ax.twinx()
        self.line_voltage, = self.ax2.plot([], [], color=VOLTAGE_COLOR, linestyle='-.', linewidth=1.5, label='Voltage (V)')
        self.line_current, = self.ax2.plot([], [], color=CURRENT_COLOR, linestyle=':', linewidth=1.5, label='Current (A)')
        self.line_power, = self.ax2.plot([], [], color=POWER_COLOR, linestyle='-.', linewidth=1.5, label='Power (W)')
        
        # Initial setup for right axis (default to Voltage)
        self.ax2.set_ylabel('Voltage (V)', color=VOLTAGE_COLOR)
        self.ax2.tick_params(axis='y', labelcolor=VOLTAGE_COLOR)
        self.line_current.set_visible(False) # Initially hide current
        self.line_power.set_visible(False)   # Initially hide power

        # Combine legends from both axes
        lines, labels = self.ax.get_legend_handles_labels()
        lines2, labels2 = self.ax2.get_legend_handles_labels()
        # Filter out hidden lines from ax2 for the initial legend
        active_lines2 = [l for l in lines2 if l.get_visible()]
        active_labels2 = [lab for l, lab in zip(lines2, labels2) if l.get_visible()]
        self.legend = self.ax.legend(lines + active_lines2, labels + active_labels2, loc='upper left')
        
        self.ax.grid(True, linestyle=':', alpha=0.7) # Grid for primary axis
        self.fig.tight_layout(pad=0.5) # Adjust layout to prevent overlap

        # Interactive elements
        self.interactive_vline = None
        self.interactive_annotation = None

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

        # Right Y-axis quantity selection
        ttk.Label(controls_frame, text="Right Axis:", style='Content.TLabel').grid(row=0, column=2, sticky='w', padx=(10,0))
        self.right_axis_options = ["Voltage (V)", "Current (A)", "Power (W)"]
        self.right_axis_var = tk.StringVar(value="Voltage (V)")
        self.right_axis_selector = ttk.Combobox(controls_frame, textvariable=self.right_axis_var,
                                                values=self.right_axis_options, state="readonly", width=12)
        self.right_axis_selector.grid(row=0, column=3, padx=5, pady=5, sticky='ew')
        self.right_axis_selector.bind("<<ComboboxSelected>>", self.on_right_axis_selection_change)
        Tooltip(self.right_axis_selector, "Select quantity for the right Y-axis.")

        # Export and Clear buttons
        self.export_btn = ttk.Button(controls_frame, text="Export CSV", command=self.export_csv, width=12)
        self.export_btn.grid(row=0, column=4, padx=5, pady=5, sticky='e') # Adjusted column
        Tooltip(self.export_btn, "Export all collected trend data to a CSV file.")

        self.clear_data_btn = ttk.Button(controls_frame, text="Clear Data", command=self.clear_data, width=12)
        self.clear_data_btn.grid(row=0, column=5, padx=5, pady=5, sticky='e') # Adjusted column
        Tooltip(self.clear_data_btn, "Clear all data from the trend graph.")
        
        # Matplotlib Navigation Toolbar
        toolbar_frame = ttk.Frame(controls_frame, style='Content.TFrame')
        toolbar_frame.grid(row=1, column=0, columnspan=6, sticky='ew', pady=(0,5)) # Adjusted columnspan
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
        self.current_data = [] 
        self.power_data = []   
        # self.start_time = time.time() # Removed, using absolute datetime objects
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_interval = 500  # ms, graph updates less frequently than heatmap

        # Configure X-axis to display time formatted in PST
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S', tz=self.PST))
        self.fig.autofmt_xdate() # Rotate date labels for better fit

        # Connect click event
        self.canvas.mpl_connect('button_press_event', self.on_canvas_click)

        self.after_id = self.after(self.update_interval, self.update_graph)

    def clear_interactive_elements(self):
        if self.interactive_vline:
            try:
                self.interactive_vline.remove()
            except (ValueError, AttributeError) as e:
                logger.warning(f'Failed to remove interactive_vline: {e}')
            self.interactive_vline = None
        
        if self.interactive_annotation:
            try:
                self.interactive_annotation.remove()
            except (ValueError, AttributeError) as e:
                logger.warning(f'Failed to remove interactive_annotation: {e}')
            self.interactive_annotation = None
        
        # Check if canvas needs redraw after removing elements
        # self.canvas.draw_idle() # Typically called by the function that initiated the clear

    def on_canvas_click(self, event):
        if event.inaxes is None:
            return
        if event.inaxes != self.ax:
            logger.warning(f'Click was in a different axes than self.ax. Proceeding anyway. event.inaxes={repr(event.inaxes)}, self.ax={repr(self.ax)}')
        if not self.time_data:
            return

        self.clear_interactive_elements()

        clicked_time_num = event.xdata
        
        time_data_nums = mdates.date2num(self.time_data)

        if not (time_data_nums.min() <= clicked_time_num <= time_data_nums.max()):
            self.canvas.draw_idle()
            return

        try:
            interp_max = np.interp(clicked_time_num, time_data_nums, self.max_data)
            interp_min = np.interp(clicked_time_num, time_data_nums, self.min_data)
            interp_avg = np.interp(clicked_time_num, time_data_nums, self.avg_data)
            # Interpolate for the selected right-axis quantity
            selected_right_label = ""
            interp_right_val = 0.0
            selected_option = self.right_axis_var.get()
            if selected_option == "Voltage (V)" and self.voltage_data:
                interp_right_val = np.interp(clicked_time_num, time_data_nums, self.voltage_data)
                selected_right_label = f"Volt: {interp_right_val:.2f}V"
            elif selected_option == "Current (A)" and self.current_data:
                interp_right_val = np.interp(clicked_time_num, time_data_nums, self.current_data)
                selected_right_label = f"Curr: {interp_right_val:.2f}A"
            elif selected_option == "Power (W)" and self.power_data:
                interp_right_val = np.interp(clicked_time_num, time_data_nums, self.power_data)
                selected_right_label = f"Pwr: {interp_right_val:.2f}W"

        except Exception as e:
            logger.error(f'Interpolation failed: {e}')
            idx = (np.abs(time_data_nums - clicked_time_num)).argmin()
            clicked_time_num = time_data_nums[idx]
            interp_max = self.max_data[idx]
            interp_min = self.min_data[idx]
            interp_avg = self.avg_data[idx]
            # Get non-interpolated value for the selected right-axis quantity
            selected_right_label = ""
            if selected_option == "Voltage (V)" and idx < len(self.voltage_data):
                interp_right_val = self.voltage_data[idx]
                selected_right_label = f"Volt: {interp_right_val:.2f}V"
            elif selected_option == "Current (A)" and idx < len(self.current_data):
                interp_right_val = self.current_data[idx]
                selected_right_label = f"Curr: {interp_right_val:.2f}A"
            elif selected_option == "Power (W)" and idx < len(self.power_data):
                interp_right_val = self.power_data[idx]
                selected_right_label = f"Pwr: {interp_right_val:.2f}W"

        clicked_time_dt = mdates.num2date(clicked_time_num, tz=self.PST)

        self.interactive_vline = self.ax.axvline(clicked_time_dt, color='dimgray', linestyle='--', linewidth=1)

        annotation_text = (
            f"Time: {clicked_time_dt.strftime('%H:%M:%S')}\n"
            f"Max: {interp_max:.2f}°C\n"
            f"Min: {interp_min:.2f}°C\n"
            f"Avg: {interp_avg:.2f}°C\n"
            f"{selected_right_label}"
        )
        self.interactive_annotation = self.ax.text(
            0.98, 0.98, 
            annotation_text, 
            transform=self.ax.transAxes, 
            fontsize=8, 
            verticalalignment='top', 
            horizontalalignment='right',
            bbox=dict(boxstyle='round,pad=0.3', fc='ivory', alpha=0.85, ec='gray')
        )
        self.canvas.draw_idle()

    def on_timespan_change(self, event=None):
        self.clear_interactive_elements()
        self.current_time_span_seconds = self.time_span_options[self.time_span_var.get()]
        self.update_graph() # Redraw with new span
        if self.interactive_vline or self.interactive_annotation:
            self.canvas.draw_idle()

    def on_right_axis_selection_change(self, event=None):
        self.clear_interactive_elements() # Clear any annotations
        selected_option = self.right_axis_var.get()

        self.line_voltage.set_visible(False)
        self.line_current.set_visible(False)
        self.line_power.set_visible(False)

        if selected_option == "Voltage (V)":
            self.ax2.set_ylabel('Voltage (V)', color=VOLTAGE_COLOR)
            self.ax2.tick_params(axis='y', labelcolor=VOLTAGE_COLOR)
            self.line_voltage.set_visible(True)
        elif selected_option == "Current (A)":
            self.ax2.set_ylabel('Current (A)', color=CURRENT_COLOR)
            self.ax2.tick_params(axis='y', labelcolor=CURRENT_COLOR)
            self.line_current.set_visible(True)
        elif selected_option == "Power (W)":
            self.ax2.set_ylabel('Power (W)', color=POWER_COLOR)
            self.ax2.tick_params(axis='y', labelcolor=POWER_COLOR)
            self.line_power.set_visible(True)
        
        # Update legend
        lines, labels = self.ax.get_legend_handles_labels()
        lines2, labels2 = self.ax2.get_legend_handles_labels()
        active_lines2 = [l for l in lines2 if l.get_visible()]
        active_labels2 = [lab for l, lab in zip(lines2, labels2) if l.get_visible()]
        if hasattr(self, 'legend') and self.legend: # Remove old legend if exists
            self.legend.remove()
        self.legend = self.ax.legend(lines + active_lines2, labels + active_labels2, loc='upper left')

        self.update_graph() # Redraw with new right axis
        if self.interactive_vline or self.interactive_annotation: # Should be cleared, but just in case
            self.canvas.draw_idle()

    def add_point(self, max_temp, min_temp, avg_temp, voltage, current, power):
        current_time = datetime.now(self.PST)
        self.time_data.append(current_time)
        self.max_data.append(max_temp)
        self.min_data.append(min_temp)
        self.avg_data.append(avg_temp)
        self.voltage_data.append(voltage)
        self.current_data.append(current)
        self.power_data.append(power)

    def update_graph(self):
        if not self.winfo_exists(): # Don't update if widget is destroyed
            return
            
        t_now_pst = datetime.now(self.PST)
        selected_right_axis = self.right_axis_var.get()

        if self.current_time_span_seconds == -1: # All Data
            plot_times = list(self.time_data)
            plot_max = list(self.max_data)
            plot_min = list(self.min_data)
            plot_avg = list(self.avg_data)
            plot_voltage = list(self.voltage_data)
            plot_current = list(self.current_data)
            plot_power = list(self.power_data)
        else:
            display_window_start_time = t_now_pst - timedelta(seconds=self.current_time_span_seconds)
            first_idx = 0
            for i, dt in enumerate(self.time_data):
                if dt >= display_window_start_time:
                    first_idx = i
                    break
            else: 
                first_idx = len(self.time_data)
            
            plot_times = self.time_data[first_idx:]
            plot_max = self.max_data[first_idx:]
            plot_min = self.min_data[first_idx:]
            plot_avg = self.avg_data[first_idx:]
            plot_voltage = self.voltage_data[first_idx:]
            plot_current = self.current_data[first_idx:]
            plot_power = self.power_data[first_idx:]

        self.line_max.set_data(plot_times, plot_max)
        self.line_min.set_data(plot_times, plot_min)
        self.line_avg.set_data(plot_times, plot_avg)
        
        # Set data for the right-axis lines based on selection
        # Only the visible one will actually be drawn due to set_visible in on_right_axis_selection_change
        self.line_voltage.set_data(plot_times, plot_voltage)
        self.line_current.set_data(plot_times, plot_current)
        self.line_power.set_data(plot_times, plot_power)
        
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
        self.clear_interactive_elements()
        self.time_data.clear()
        self.max_data.clear()
        self.min_data.clear()
        self.avg_data.clear()
        self.voltage_data.clear() # Clear voltage data
        self.current_data.clear()
        self.power_data.clear()
        self.update_graph() # Redraw empty graph, which will now set axes based on current time
        if self.interactive_vline or self.interactive_annotation:
            self.canvas.draw_idle()
        self.set_status("Trend graph data cleared.")

    def export_csv(self, sample_name: str | None = None):
        if not self.time_data:
            self.set_status("No data to export.")
            return
        
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        
        if sample_name and sample_name.strip():
            s_name = sample_name.strip().replace(" ", "_") # Sanitize for filename
            filename = f"{s_name}_trend_{timestamp}.csv"
        else:
            filename = f"trend_{timestamp}.csv"

        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp (PST)', 'Max Temp (C)', 'Min Temp (C)', 'Avg Temp (C)', 'Voltage (V)', 'Current (A)', 'Power (W)']) # Updated header
                for dt_obj, mx, mn, av, v, c, p in zip(self.time_data, self.max_data, self.min_data, self.avg_data, self.voltage_data, self.current_data, self.power_data):
                    # Format datetime object to string including PST
                    timestamp_str = dt_obj.strftime('%Y-%m-%d %H:%M:%S %Z')
                    writer.writerow([timestamp_str, mx, mn, av, v, c, p]) # Write formatted timestamp
            self.set_status(f"Graph data exported to {filename}")
        except Exception as e:
            self.set_status(f"Export failed: {e}")

    def stop(self):
        if self.after_id:
            self.after_cancel(self.after_id)