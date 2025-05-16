import tkinter as tk
from tkinter import ttk
from tkinter import Canvas
from .control_panel import ControlPanel
from .heatmap_view import HeatmapView
from .trend_graph import TrendGraph
from .utils import Tooltip
from .status_bar_view import StatusBarView
# Assuming CameraManager can be imported (it's in devices/)
# If app.py is in ui/, and devices/ is a sibling to ui/, then:
# import sys
# sys.path.append('..') # Add parent directory to sys.path
# from devices.camera_manager import CameraManager 
# A better way is to ensure your project is structured as a package or PYTHONPATH is set.
# For now, assuming it can be found or will be adjusted later.
# Let's assume direct import works if project is run from root where both ui and devices are top-level or in path.
# from devices.camera_manager import CameraManager # This might fail depending on execution context.
# For robustness in typical project structures:
import sys
import os
# Add the parent directory of 'ui' to the Python path
# This allows importing from sibling directories like 'devices'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
from devices.camera_manager import CameraManager
from devices.data_aggregator import DataAggregator # Added for type hinting if needed, SenxorApp already gets pid which has it
import time # Added for PID output update timestamp
import math
import numpy as np
import config


class SenxorApp(ttk.Frame):
    def __init__(self, master, camera_manager: CameraManager, siggen, pid):
        super().__init__(master)
        self.master = master
        self.camera_manager = camera_manager
        self.siggen = siggen
        self.pid = pid # pid already has a reference to data_aggregator
        # We need to pass camera_manager and the pid's data_aggregator to ControlPanel
        self.data_aggregator = pid.data_aggregator # Get it from PID for consistency
        if self.data_aggregator is None:
            # This case should ideally not happen if main.py sets it up correctly.
            # Fallback or error if PID wasn't given an aggregator.
            print("CRITICAL WARNING: PID has no DataAggregator. ControlPanel PID source config will fail.")
            # You might want to create a dummy aggregator or raise an error depending on desired robustness.
            # For now, ControlPanel will receive None and should handle it gracefully.

        # Main application frame fills the master window
        self.pack(fill='both', expand=True)

        self.master.geometry('1300x750')
        self.master.title("Senxor Thermal Control & Analysis - Multi-Camera")

        # Ensure signal generator is set to 0V on app close
        self.master.protocol("WM_DELETE_WINDOW", self._on_app_close)

        # --- Modern Theme and Colors ---
        style = ttk.Style()
        style.theme_use('clam')

        # Define color palette
        COLOR_BACKGROUND = '#ECEFF1'      # Light Blue Grey - Main window bg
        COLOR_FRAME_BG = '#CFD8DC'        # Blue Grey - Frame/Labelframe bg
        COLOR_TEXT = '#263238'           # Dark Blue Grey - General text
        COLOR_TEXT_LIGHT = '#546E7A'     # Lighter text for secondary info
        COLOR_PRIMARY_ACCENT = '#00796B'  # Teal - Primary buttons
        COLOR_SECONDARY_ACCENT = '#546E7A'# Blue Grey - Secondary buttons
        COLOR_HIGHLIGHT = '#FFAB40'       # Orange - Accents, e.g., ON state, hot marker
        COLOR_TOOLTIP_BG = '#455A64'      # Darker Blue Grey for tooltip bg
        COLOR_TOOLTIP_TEXT = '#FFFFFF'    # White for tooltip text

        # General widget styling
        style.configure('.', font=('Segoe UI', 10), foreground=COLOR_TEXT)

        style.configure('TFrame', background=COLOR_BACKGROUND)
        style.configure('Content.TFrame', background=COLOR_FRAME_BG) # For content areas

        style.configure('TLabel', background=COLOR_BACKGROUND, font=('Segoe UI', 10))
        style.configure('Content.TLabel', background=COLOR_FRAME_BG, font=('Segoe UI', 10))
        style.configure('Status.TLabel', background=COLOR_BACKGROUND, font=('Segoe UI', 9), foreground=COLOR_TEXT_LIGHT, padding=(5,3))

        style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=(10, 5), foreground='white', background=COLOR_SECONDARY_ACCENT, borderwidth=0)
        style.map('TButton',
            background=[('active', COLOR_SECONDARY_ACCENT), ('pressed', COLOR_PRIMARY_ACCENT)],
            relief=[('pressed', 'sunken'), ('!pressed', 'flat')])
        
        style.configure('Primary.TButton', background=COLOR_PRIMARY_ACCENT)
        style.map('Primary.TButton',
            background=[('active', COLOR_PRIMARY_ACCENT), ('pressed', COLOR_HIGHLIGHT)])

        style.configure('TCheckbutton', background=COLOR_BACKGROUND, font=('Segoe UI', 10))
        style.map('TCheckbutton', indicatorcolor=[('selected', COLOR_PRIMARY_ACCENT), ('!selected', 'white')])

        style.configure('TLabelframe', background=COLOR_FRAME_BG, font=('Segoe UI', 11, 'bold'), bordercolor=COLOR_TEXT_LIGHT, foreground=COLOR_TEXT, relief='groove')
        style.configure('TLabelframe.Label', background=COLOR_FRAME_BG, font=('Segoe UI', 11, 'bold'), foreground=COLOR_TEXT, padding=(5,2))

        style.configure('TSpinbox', font=('Segoe UI', 10), padding=(5,3), borderwidth=1, relief='solid') # May need to handle arrow styling if possible
        style.configure('TEntry', font=('Segoe UI', 10), padding=(5,3))
        style.configure('TOptionMenu', font=('Segoe UI', 10), padding=(5,3))
        style.configure('TScale', background=COLOR_FRAME_BG)

        # Configure Tooltip style (assuming Tooltip class will be adapted to use a ttk.Label)
        Tooltip.configure_style(style, 'App.Tooltip.TLabel', 
                                background=COLOR_TOOLTIP_BG, 
                                foreground=COLOR_TOOLTIP_TEXT, 
                                font=('Segoe UI', 9)
                                # borderwidth=1, relief='solid', bordercolor=COLOR_SECONDARY_ACCENT # Temporarily removed for testing
                                )

        # --- Shared Camera View Settings Variables ---
        # Initialize these variables here to be used by both the settings panel and heatmap views
        self.hot_smooth_len_var = tk.IntVar(value=config.HOT_SMOOTH_LEN_DEFAULT)
        self.cold_smooth_len_var = tk.IntVar(value=config.COLD_SMOOTH_LEN_DEFAULT)
        self.sample_number_var = tk.StringVar()
        self.colormap_var = tk.StringVar(value=config.DEFAULT_COLORMAP)
        self.show_hot_spot_var = tk.BooleanVar(value=True)
        self.show_cold_spot_var = tk.BooleanVar(value=False)
        # Global Max Voltage
        self.max_voltage_var = tk.DoubleVar(value=config.MAX_VOLTAGE_DEFAULT)

        # Trace smoothing changes to update heatmap views
        def _propagate_smoothing(*args):
            for hv in getattr(self, 'heatmap_views', []):
                hv.on_smooth_len_change()
        self.hot_smooth_len_var.trace_add('write', _propagate_smoothing)
        self.cold_smooth_len_var.trace_add('write', _propagate_smoothing)
        
        # --- Scrollable Area Setup ---
        # Outer frame to hold canvas and scrollbar
        scroll_outer_frame = ttk.Frame(self, style='TFrame')
        scroll_outer_frame.pack(fill='both', expand=True, padx=10, pady=10)
        scroll_outer_frame.grid_rowconfigure(0, weight=1)
        scroll_outer_frame.grid_columnconfigure(0, weight=1)

        # Canvas widget
        self.canvas = Canvas(scroll_outer_frame, bg=COLOR_FRAME_BG, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')

        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(scroll_outer_frame, orient='vertical', command=self.canvas.yview)
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=v_scrollbar.set)

        # Frame inside the canvas that will contain the actual content
        self.scrollable_inner_frame = ttk.Frame(self.canvas, style='Content.TFrame')
        self.canvas.create_window((0, 0), window=self.scrollable_inner_frame, anchor='nw', tags="scrollable_frame")

        # Update scrollregion when the inner frame size changes
        self.scrollable_inner_frame.bind("<Configure>", self._on_inner_frame_configure)

        # Bind mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

        # --- Content Layout within the Scrollable Frame ---
        # Configure columns: col 0 for content, col 1 for potential future use or alignment
        self.scrollable_inner_frame.columnconfigure(0, weight=1)
        self.scrollable_inner_frame.columnconfigure(1, weight=0) # Settings button goes here

        # --- Row 0: Status Bar and Settings Button ---
        status_settings_frame = ttk.Frame(self.scrollable_inner_frame, style='TFrame') # Use TFrame for background match
        status_settings_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0,5))
        status_settings_frame.columnconfigure(0, weight=1) # Status bar takes available space
        status_settings_frame.columnconfigure(1, weight=0) # Button takes fixed space

        self.status_bar_view = StatusBarView(status_settings_frame, style='TFrame')
        self.status_bar_view.grid(row=0, column=0, sticky='ew')
        status_update_method = self.status_bar_view.set_status

        self.settings_btn = ttk.Button(status_settings_frame, text='⚙ Settings', command=self._toggle_settings_panel, style='TButton')
        self.settings_btn.grid(row=0, column=1, sticky='e', padx=(10,0))
        Tooltip(self.settings_btn, "Show/Hide Display Settings Panel")

        # --- Row 1: Settings Panel (Hidden by default) ---
        self.settings_panel_visible = False
        self._create_settings_panel(style) # Will place itself in row 1

        # --- Row 2: PanedWindow (Controls + Cameras) ---
        self.top_paned = ttk.PanedWindow(self.scrollable_inner_frame, orient='horizontal')
        self.top_paned.grid(row=2, column=0, columnspan=2, sticky='nsew', pady=(0,10))

        # Control Panel
        self.control_panel = ControlPanel(self.top_paned, 
                                          pid=self.pid, 
                                          siggen=self.siggen, 
                                          camera_manager=self.camera_manager, 
                                          data_aggregator=self.data_aggregator,
                                          set_status=status_update_method, 
                                          style='Content.TFrame',
                                          max_voltage_var=self.max_voltage_var)
        
        # Camera Display Area Frame
        self.camera_frame = ttk.Frame(self.top_paned, style='Content.TFrame')
        # Configure self.camera_frame to have a row for controls and a row for the camera grid
        self.camera_frame.rowconfigure(0, weight=0) # Row for master controls (snapshot button)
        self.camera_frame.rowconfigure(1, weight=1) # Row for the actual camera grid
        self.camera_frame.columnconfigure(0, weight=1) # Ensure the content can expand width-wise

        # Initialize Master Camera Controls (Snapshot button etc.)
        # This will place its controls_frame in self.camera_frame at row=0
        self._init_master_camera_controls(style)

        # Create a dedicated frame for the grid of camera views
        self.camera_grid_frame = ttk.Frame(self.camera_frame, style='Content.TFrame')
        self.camera_grid_frame.grid(row=1, column=0, sticky='nsew')
        # Ensure the grid frame itself also allows its internal grid to expand
        self.camera_grid_frame.rowconfigure(0, weight=1) # Default, adjust in populate if multi-row cameras
        self.camera_grid_frame.columnconfigure(0, weight=1) # Default, adjust in populate if multi-col cameras

        self.heatmap_views = []
        # Populate cameras into self.camera_grid_frame
        self.after(0, self._populate_camera_views)

        # Add panels to PanedWindow
        self.top_paned.add(self.control_panel, weight=1)
        self.top_paned.add(self.camera_frame,   weight=2)
        
        # --- Row 3: Trend Graph ---
        self.trend_graph = TrendGraph(self.scrollable_inner_frame, set_status=status_update_method, style='Content.TFrame')
        self.trend_graph.grid(row=3, column=0, columnspan=2, sticky='nsew')

        # Configure row weights *within* the scrollable frame
        self.scrollable_inner_frame.rowconfigure(0, weight=0)  # Status/Settings Btn row
        self.scrollable_inner_frame.rowconfigure(1, weight=0)  # Settings Panel (dynamically managed)
        self.scrollable_inner_frame.rowconfigure(2, weight=1)  # Paned window (CP + Heatmap)
        self.scrollable_inner_frame.rowconfigure(3, weight=1)  # Trend graph

        # Set initial PanedWindow sash position
        self.after(100, self.set_initial_pane_proportions)
        
        # Configure trend graph export
        self.trend_graph.export_btn.configure(command=self._export_trend_data_coordinated)

        # --- Start hotplug monitor ---
        self.camera_manager.start_hotplug_monitor(on_change=self._on_camera_hotplug)

        # --- Start PID output loop ---
        pid_sample_ms = max(10, int(self.pid.sample_time * 1000))
        self.after(pid_sample_ms, self._update_pid_output)

        self.last_pid_output_time = 0

        # Bind canvas width change to update the inner frame width
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Hot/Cold Spot Overlay Checkboxes
        hot_chk = ttk.Checkbutton(self.settings_panel, text='Show Hot Spot Overlay', variable=self.show_hot_spot_var, style='TCheckbutton')
        hot_chk.grid(row=4, column=0, columnspan=2, sticky='w', padx=5, pady=(10,2))
        Tooltip(hot_chk, "Toggle the display of the hot spot marker on the heatmap.")
        cold_chk = ttk.Checkbutton(self.settings_panel, text='Show Cold Spot Overlay', variable=self.show_cold_spot_var, style='TCheckbutton')
        cold_chk.grid(row=5, column=0, columnspan=2, sticky='w', padx=5, pady=(2,10))
        Tooltip(cold_chk, "Toggle the display of the cold spot marker on the heatmap.")

        # Propagate overlay settings to all heatmap views
        def _propagate_overlay(*args):
            for hv in getattr(self, 'heatmap_views', []):
                hv.show_hot_spot_var = self.show_hot_spot_var
                hv.show_cold_spot_var = self.show_cold_spot_var
                hv.update_image()  # Force redraw
        self.show_hot_spot_var.trace_add('write', _propagate_overlay)
        self.show_cold_spot_var.trace_add('write', _propagate_overlay)

        # --- Trend Graph Aggregation Update ---
        self.trend_graph_update_interval = config.TREND_GRAPH_UPDATE_MS  # ms
        self.after(self.trend_graph_update_interval, self._update_trend_graph_aggregation)

    def _on_canvas_configure(self, event):
        """Dynamically set the width of the inner frame to match the canvas width."""
        canvas_width = event.width
        self.canvas.itemconfig("scrollable_frame", width=canvas_width)

    def _on_inner_frame_configure(self, event):
        """Update the scrollregion of the canvas to encompass the inner frame."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mouse wheel scrolling across different platforms."""
        if event.num == 4: # Linux scroll up
            delta = -1 
        elif event.num == 5: # Linux scroll down
            delta = 1
        else: # Windows/macOS
            delta = -1 * int(event.delta / 120) # Normalize wheel delta
        
        self.canvas.yview_scroll(delta, "units")

    def _populate_camera_views(self):
        """Populate/refresh the camera display area with a stacked list of HeatmapViews
        into the self.camera_grid_frame."""

        # Clear previous widgets FROM THE CAMERA GRID FRAME ONLY
        for child in self.camera_grid_frame.winfo_children():
            child.destroy()

        self.heatmap_views.clear()

        active_cameras = self.camera_manager.get_all_cameras()
        # Sort by serial number (camera_id_hexsn or sn)
        def serial_key(cam):
            serial = None
            if hasattr(cam, 'mi48') and cam.mi48:
                serial = getattr(cam.mi48, 'camera_id_hexsn', None) or getattr(cam.mi48, 'sn', None)
            order_list = getattr(config, 'CAMERA_SERIAL_ORDER', [])
            if serial in order_list:
                return order_list.index(serial)
            # If not in predefined order, sort after the defined ones
            return len(order_list) + (0 if serial is None else hash(serial) & 0xFFFF_FFFF)
        active_cameras = sorted(active_cameras, key=serial_key)

        if not active_cameras:
            # Place "No cameras" message inside the camera_grid_frame
            no_cam_frame = ttk.Frame(self.camera_grid_frame, style='Content.TFrame')
            msg_label = ttk.Label(
                no_cam_frame,
                text="No cameras available or started.",
                style='Content.TLabel',
                font=('Segoe UI', 12)
            )
            msg_label.pack(padx=20, pady=20, expand=True, anchor='center')
            no_cam_frame.pack(fill='both', expand=True) # Pack into no_cam_frame
            # no_cam_frame needs to be gridded or packed into camera_grid_frame if not already
            # If using pack above, ensure no_cam_frame expands in camera_grid_frame
            # For consistency with grid elsewhere, let's grid it.
            # no_cam_frame.grid(row=0, column=0, sticky='nsew') # This might conflict if camera_grid_frame uses grid later
            # Simpler: just have the msg_label pack directly into camera_grid_frame if it's the only thing
            # For robustness, let's ensure no_cam_frame is the one taking space in camera_grid_frame
            self.camera_grid_frame.columnconfigure(0, weight=1)
            self.camera_grid_frame.rowconfigure(0, weight=1)
            no_cam_frame.grid(row=0, column=0, sticky='nsew')
            return

        # Determine tiling dimensions (max 2 columns)
        cols = min(2, len(active_cameras))
        rows = math.ceil(len(active_cameras) / cols)

        # Ensure grid columns stretch evenly IN THE CAMERA GRID FRAME
        for c in range(cols):
            self.camera_grid_frame.columnconfigure(c, weight=1)
        # Rows for cameras in CAMERA GRID FRAME
        for r_idx in range(rows): # Renamed r to r_idx to avoid conflict with outer scope r if any
            self.camera_grid_frame.rowconfigure(r_idx, weight=1)


        # Compute tile size respecting aspect ratio (80x62) and max half-screen height
        self.camera_grid_frame.update_idletasks()  # Get accurate frame width of camera_grid_frame
        available_w = max(1, self.camera_grid_frame.winfo_width())
        padding_px = 10
        tile_w = max(1, int((available_w - (cols + 1) * padding_px) / cols))
        TILE_RATIO = 62 / 80  # height / width
        tile_h = max(1, int(tile_w * TILE_RATIO))

        screen_h = self.master.winfo_screenheight()
        max_total_h = int(screen_h * 0.4) # Limit camera view height a bit more if needed

        # If tiles would exceed max height, shrink them proportionally
        if tile_h * rows + (rows + 1) * padding_px > max_total_h:
            if rows > 0:  # Avoid division by zero if rows is 0
             tile_h = int((max_total_h - (rows + 1) * padding_px) / rows)
             tile_w = max(1, int(tile_h / TILE_RATIO))
            else:  # Should not happen if active_cameras is not empty
                tile_h = 50  # Fallback
                tile_w = int(tile_h / TILE_RATIO)


        # Create a HeatmapView for each connected camera and position it on the grid
        for i, cam_instance in enumerate(active_cameras):
            r_loop, c_loop = divmod(i, cols)
            camera_container = ttk.Frame(self.camera_grid_frame, style='Content.TFrame', padding=(5, 5))
            camera_container.grid(row=r_loop, column=c_loop, sticky='nsew', padx=padding_px, pady=padding_px)
            # COM-port / identifier label
            port_name = cam_instance.connected_port or f"ID-{i}"
            serial_number = None
            if hasattr(cam_instance, 'mi48') and cam_instance.mi48:
                serial_number = getattr(cam_instance.mi48, 'camera_id_hexsn', None) or getattr(cam_instance.mi48, 'sn', None)
            friendly_name = None
            if serial_number:
                friendly_name = getattr(config, 'CAMERA_NAME_MAP', {}).get(serial_number, None)
            if serial_number and friendly_name:
                label_text = f"{friendly_name} ({port_name})"
            elif serial_number:
                label_text = f"{port_name}"
            else:
                label_text = port_name
            title_lbl = ttk.Label(
                camera_container,
                text=label_text,
                style='Content.TLabel',
                font=('Segoe UI', 11, 'bold')
            )
            title_lbl.pack(anchor='w', pady=(0, 2))

            # Heatmap view
            heatmap_view_instance = HeatmapView(
                camera_container,
                camera=cam_instance,
                trend_graph=None,
                set_status=self.status_bar_view.set_status,
                style='Content.TFrame',
                show_controls=True,  # show per-camera controls (including rotate)
                colormap_var=self.colormap_var,
                hot_smooth_len_var=self.hot_smooth_len_var,
                cold_smooth_len_var=self.cold_smooth_len_var
            )
            heatmap_view_instance.pack(fill='both', expand=True)

            # Share master control variables with this heatmap view
            heatmap_view_instance.hot_smooth_len_var = self.hot_smooth_len_var
            heatmap_view_instance.cold_smooth_len_var = self.cold_smooth_len_var
            heatmap_view_instance.colormap_var = self.colormap_var
            heatmap_view_instance.sample_number_var = self.sample_number_var
            heatmap_view_instance.show_hot_spot_var = self.show_hot_spot_var
            heatmap_view_instance.show_cold_spot_var = self.show_cold_spot_var

            # Enforce target size & aspect ratio
            if hasattr(heatmap_view_instance, 'set_target_size'):
                heatmap_view_instance.set_target_size(tile_w, tile_h)

            # Keep reference
            self.heatmap_views.append(heatmap_view_instance)

    def set_initial_pane_proportions(self):
        self.update_idletasks()
        try:
            total_w = self.top_paned.winfo_width()
            # Set sash so control panel is about 60% and heatmap 40%
            # Ensure it doesn't fail if winfo_width is 0 or paned children not ready
            if total_w > 0 and len(self.top_paned.panes()) == 2: 
                 self.top_paned.sashpos(0, int(total_w * 0.6))
        except tk.TclError: # Handles cases where widget might not be fully initialized
            self.after(100, self.set_initial_pane_proportions) # Retry

    def set_status(self, msg):
        if hasattr(self, 'status_bar_view') and self.status_bar_view: # Check if it exists
            self.status_bar_view.set_status(msg)
        else: # Fallback if called before status_bar_view is initialized (should not happen in normal flow)
            print(f"Status (early): {msg}")

    def _export_trend_data_coordinated(self):
        sample_name = ""
        # If multiple heatmaps, which one provides the sample name?
        # For now, use the first one if available, or let user select later.
        if self.heatmap_views:
            # Default to first heatmap view when multiple are present
            sample_name = self.heatmap_views[0].get_sample_number()
        
        if hasattr(self, 'trend_graph') and self.trend_graph:
            self.trend_graph.export_csv(sample_name=sample_name) 

    def refresh_camera_views(self):
        """Trigger a refresh of the camera display. Safe to call from non-UI threads."""
        self.after(0, self._populate_camera_views)

    def _on_camera_hotplug(self):
        print("SenxorApp: Camera hotplug event detected. Refreshing camera views...")
        self.refresh_camera_views() 

    def _update_pid_output(self):
        """Periodically calculates PID output and applies it to the signal generator."""
        if not self.pid: # Safety check
            return 

        reschedule_delay_ms = max(10, int(self.pid.sample_time * 1000))

        try:
            if self.pid.auto_mode:
                # Calculate PID output (must be called to update PID state)
                voltage = self.pid() 

                # --- Save-on-setpoint logic for standard PID mode ---
                # Get current temperature using the same aggregation mode as PID input
                agg_mode = getattr(self.control_panel, 'pid_agg_mode_var', None)
                if agg_mode is not None:
                    agg_mode = agg_mode.get()
                if not agg_mode:
                    agg_mode = 'overall_max'
                temp = None
                if hasattr(self, 'data_aggregator') and self.data_aggregator:
                    temp = self.data_aggregator.get_frames_for_pid(aggregation_mode=agg_mode)
                if hasattr(self, 'control_panel') and hasattr(self.control_panel, '_pid_setpoint_check'):
                    self.control_panel._pid_setpoint_check(temp)

                # Apply to signal generator if open and sufficient time has passed
                if self.siggen and self.siggen.is_open:
                    # Optional: Check time elapsed since last update to avoid flooding siggen
                    # current_time = time.time()
                    # if current_time - self.last_pid_output_time >= self.pid.sample_time:
                    try:
                        self.siggen.set_voltage(voltage)
                        # self.last_pid_output_time = current_time # Update last sent time
                        # Optional: Provide feedback via status bar?
                        # self.set_status(f"PID Output: {voltage:.3f} V") 
                    except Exception as e:
                        self.set_status(f"SigGen Error: Failed to set voltage ({e})")
                        print(f"SigGen Error: {e}") # Also print for debugging
                
                # Note: TrendGraph update happens in HeatmapView currently with placeholder voltage.
                # If we want accurate voltage on the graph, we need to update it here or pass voltage down.
                # Example: self.trend_graph.update_last_voltage(voltage) - requires TrendGraph modification.

        except Exception as e:
            self.set_status(f"PID Error: Failed during calculation/update ({e})")
            print(f"PID Error: {e}")
        finally:
            # Reschedule the next update
            self.after(reschedule_delay_ms, self._update_pid_output) 

    # ----------------- Master Controls (Simplified) -----------------
    def _init_master_camera_controls(self, style):
        # This frame now sits ABOVE the camera views grid (self.camera_grid_frame)
        # It is placed in self.camera_frame at row=0.

        # controls_frame is parented to self.camera_frame (the overall container for this section)
        controls_frame = ttk.Frame(self.camera_frame, style='Content.TFrame', padding=(5,5))
        controls_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=(5,0)) # pady bottom 0 to be close to grid

        # Configure layout - Make the snapshot button align to the right
        controls_frame.columnconfigure(0, weight=1) # Empty space pushes button right
        controls_frame.columnconfigure(1, weight=0) # Button takes needed space

        # Save All Data button
        save_all_btn = ttk.Button(controls_frame, text="Save All Data", command=self._save_all_data, style='Primary.TButton')
        save_all_btn.grid(row=0, column=2, padx=5, pady=2, sticky='e')
        Tooltip(save_all_btn, "Save trend graph data and all camera data to a dated folder.")

    def _save_all_data(self):
        import os
        import time
        from tkinter import messagebox
        # Create a folder with the current date and time
        timestamp = time.strftime('%Y%m%d-%H%M%S')
        folder_name = f"capture_{timestamp}"
        os.makedirs(folder_name, exist_ok=True)

        # Save trend graph data
        try:
            sample_name = self.sample_number_var.get().strip()
            # Use sample name in trend graph filename
            trend_graph_filename = f"{sample_name}_trend_graph.csv" if sample_name else "trend_graph.csv"
            trend_graph_path = os.path.join(folder_name, trend_graph_filename)
            self.trend_graph.export_csv(sample_name=sample_name, output_path=trend_graph_path)
        except Exception as e:
            messagebox.showerror("Save All Data", f"Failed to save trend graph data: {e}")
            return

        # Save all camera snapshots
        num_saved = 0
        failed_cams = []
        failed_msgs = []
        if not self.heatmap_views:
            messagebox.showerror("Save All Data", "No active cameras found.")
            return
        orig_cwd = os.getcwd()
        try:
            os.chdir(folder_name)
            for i, hv in enumerate(self.heatmap_views):
                # Get camera friendly name
                camera_name = None
                serial_number = None
                if hasattr(hv.camera, 'mi48') and hv.camera.mi48:
                    serial_number = getattr(hv.camera.mi48, 'camera_id_hexsn', None) or getattr(hv.camera.mi48, 'sn', None)
                if serial_number:
                    camera_name = getattr(config, 'CAMERA_NAME_MAP', {}).get(serial_number, None)
                if not camera_name:
                    camera_name = f"Camera{i+1}"
                camera_name_safe = camera_name.replace(" ", "_").replace("/", "-")
                try:
                    orig_sample = hv.sample_number_var.get()
                    hv.sample_number_var.set(f"{sample_name}" if sample_name else "snapshot")
                    hv.save_snapshot()
                    hv.sample_number_var.set(orig_sample)
                    num_saved += 1
                except Exception as e:
                    failed_cams.append(camera_name_safe)
                    failed_msgs.append(f"{camera_name_safe}: {e}")
            if num_saved > 0 and not failed_cams:
                messagebox.showinfo("Save All Data", f"Trend graph and all camera snapshots saved in '{folder_name}'.")
            elif num_saved > 0 and failed_cams:
                messagebox.showwarning("Save All Data", f"Trend graph and some camera snapshots saved in '{folder_name}'. Failed for: {', '.join(failed_cams)}.\n{chr(10).join(failed_msgs)}")
            elif failed_cams:
                messagebox.showerror("Save All Data", f"Failed to save camera snapshots: {', '.join(failed_cams)}.\n{chr(10).join(failed_msgs)}")
        finally:
            os.chdir(orig_cwd)

    def _create_settings_panel(self, style):
        self.settings_panel = ttk.LabelFrame(self.scrollable_inner_frame, text="Display Settings", style='TLabelframe', padding=(10,10))
        # Position in row 1, spanning columns
        self.settings_panel.grid(row=1, column=0, columnspan=2, sticky='new', padx=10, pady=(5,10))
        self.settings_panel.grid_remove() # Hide by default

        # Configure columns within the settings panel for layout
        self.settings_panel.columnconfigure(0, weight=0) # Labels
        self.settings_panel.columnconfigure(1, weight=1) # Controls (expand)
        self.settings_panel.columnconfigure(2, weight=0) # Value display for sliders

        # Colormap selector
        ttk.Label(self.settings_panel, text='Colormap:', style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=5, pady=5)
        cmap_menu = ttk.OptionMenu(self.settings_panel, self.colormap_var, self.colormap_var.get(), 'Jet','Hot','Magma','Inferno','Plasma','Viridis','Cividis','Twilight','Turbo')
        cmap_menu.grid(row=0, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(cmap_menu, "Select the color palette for the thermal display.")

        # Sample Number
        ttk.Label(self.settings_panel, text='Sample #:', style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=5, pady=5)
        sample_entry = ttk.Entry(self.settings_panel, textvariable=self.sample_number_var, width=15)
        sample_entry.grid(row=1, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(sample_entry, "Identifier for the current sample/test run (used in snapshot filenames).")

        # Smoothing sliders - Hot
        ttk.Label(self.settings_panel, text='Hot Spot Smooth (frames):', style='Content.TLabel').grid(row=2, column=0, sticky='w', padx=5, pady=5)
        hot_slider = ttk.Scale(self.settings_panel, from_=1, to=30, variable=self.hot_smooth_len_var, orient='horizontal', length=150)
        hot_slider.grid(row=2, column=1, sticky='ew', padx=5, pady=5)
        ttk.Label(self.settings_panel, textvariable=self.hot_smooth_len_var, style='Content.TLabel', width=3).grid(row=2, column=2, sticky='w', padx=(0, 5))
        Tooltip(hot_slider, "Number of frames to average for the hot spot marker position (1-30).")

        # Smoothing sliders - Cold
        ttk.Label(self.settings_panel, text='Cold Spot Smooth (frames):', style='Content.TLabel').grid(row=3, column=0, sticky='w', padx=5, pady=5)
        cold_slider = ttk.Scale(self.settings_panel, from_=1, to=30, variable=self.cold_smooth_len_var, orient='horizontal', length=150)
        cold_slider.grid(row=3, column=1, sticky='ew', padx=5, pady=5)
        ttk.Label(self.settings_panel, textvariable=self.cold_smooth_len_var, style='Content.TLabel', width=3).grid(row=3, column=2, sticky='w', padx=(0, 5))
        Tooltip(cold_slider, "Number of frames to average for the cold spot marker position (1-30).")

        # Hot/Cold Spot Overlay Checkboxes
        hot_chk = ttk.Checkbutton(self.settings_panel, text='Show Hot Spot Overlay', variable=self.show_hot_spot_var, style='TCheckbutton')
        hot_chk.grid(row=4, column=0, columnspan=2, sticky='w', padx=5, pady=(10,2))
        Tooltip(hot_chk, "Toggle the display of the hot spot marker on the heatmap.")
        cold_chk = ttk.Checkbutton(self.settings_panel, text='Show Cold Spot Overlay', variable=self.show_cold_spot_var, style='TCheckbutton')
        cold_chk.grid(row=5, column=0, columnspan=2, sticky='w', padx=5, pady=(2,10))
        Tooltip(cold_chk, "Toggle the display of the cold spot marker on the heatmap.")

        # Max Voltage (global)
        ttk.Label(self.settings_panel, text='Max Voltage (V):', style='Content.TLabel').grid(row=6, column=0, sticky='w', padx=5, pady=5)
        max_voltage_spin = ttk.Spinbox(self.settings_panel, from_=0, to=20, increment=0.1, textvariable=self.max_voltage_var, width=8)
        max_voltage_spin.grid(row=6, column=1, sticky='ew', padx=5, pady=5)
        Tooltip(max_voltage_spin, "Global maximum voltage allowed for all operations (default 5V).")

    def _toggle_settings_panel(self):
        self.settings_panel_visible = not self.settings_panel_visible
        if self.settings_panel_visible:
            self.settings_panel.grid() # Show the panel
            # Optionally, adjust row weights if needed, but grid() should be enough if rowconfigure is set
        else:
            self.settings_panel.grid_remove() # Hide the panel
        # Force geometry update to reflect potential changes
        self.scrollable_inner_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all")) 

    def _update_trend_graph_aggregation(self):
        """Aggregate camera data according to aggregation mode and update the trend graph."""
        # Get aggregation mode from control panel (default to overall_max)
        agg_mode = getattr(self.control_panel, 'pid_agg_mode_var', None)
        if agg_mode is not None:
            agg_mode = agg_mode.get()
        if not agg_mode:
            agg_mode = 'overall_max'

        # Gather latest frames from all heatmap views
        frames = []
        for hv in self.heatmap_views:
            if hv.last_frame is not None:
                frames.append(hv.last_frame)
        if not frames:
            # No data to plot
            self.after(self.trend_graph_update_interval, self._update_trend_graph_aggregation)
            return

        # Stack frames for aggregation
        try:
            stacked = np.stack(frames)
        except Exception:
            self.after(self.trend_graph_update_interval, self._update_trend_graph_aggregation)
            return

        # Compute aggregated values
        if agg_mode == 'overall_max':
            agg_max = float(np.max(stacked))
            agg_min = float(np.min(stacked))
            agg_avg = float(np.mean(stacked))
        elif agg_mode == 'average_mean':
            agg_max = float(np.mean(np.max(stacked, axis=(1,2))))
            agg_min = float(np.mean(np.min(stacked, axis=(1,2))))
            agg_avg = float(np.mean(stacked))
        elif agg_mode == 'first_valid_mean':
            # Use the first frame as the source
            agg_max = float(np.max(stacked[0]))
            agg_min = float(np.min(stacked[0]))
            agg_avg = float(np.mean(stacked[0]))
        else:
            # Fallback to overall_max
            agg_max = float(np.max(stacked))
            agg_min = float(np.min(stacked))
            agg_avg = float(np.mean(stacked))

        # Voltage: if available from PID or siggen, otherwise 0.0
        voltage = 0.0
        if hasattr(self, 'siggen') and hasattr(self.siggen, 'current_voltage'):
            voltage = float(getattr(self.siggen, 'current_voltage', 0.0))
        elif hasattr(self, 'pid') and hasattr(self.pid, 'last_output'):
            voltage = float(getattr(self.pid, 'last_output', 0.0))

        self.trend_graph.add_point(agg_max, agg_min, agg_avg, voltage)
        self.after(self.trend_graph_update_interval, self._update_trend_graph_aggregation) 

    def _on_app_close(self):
        try:
            if hasattr(self, 'siggen') and self.siggen and getattr(self.siggen, 'is_open', False):
                self.siggen.set_voltage(0.0)
        except Exception as e:
            print(f"Error setting signal generator to 0V on close: {e}")
        self.master.destroy() 