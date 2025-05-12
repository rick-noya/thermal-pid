import tkinter as tk
from tkinter import ttk
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

        self.pack(fill='both', expand=True)

        self.master.geometry('1300x750')
        self.master.title("Senxor Thermal Control & Analysis - Multi-Camera")

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

        # Main layout panels
        main_content_frame = ttk.Frame(self, style='Content.TFrame')
        main_content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.status_bar_view = StatusBarView(main_content_frame, style='TFrame')
        self.status_bar_view.grid(row=0, column=0, sticky='ew', pady=(0,5))

        status_update_method = self.status_bar_view.set_status

        # Top row: PanedWindow for control panel and the new camera display area
        self.top_paned = ttk.PanedWindow(main_content_frame, orient='horizontal')
        self.top_paned.grid(row=1, column=0, sticky='nsew', pady=(0,10))

        # Pass camera_manager and data_aggregator to ControlPanel
        self.control_panel = ControlPanel(self.top_paned, 
                                          pid=self.pid, 
                                          siggen=self.siggen, 
                                          camera_manager=self.camera_manager, 
                                          data_aggregator=self.data_aggregator, # Pass the aggregator
                                          set_status=status_update_method, 
                                          style='Content.TFrame')
        
        # --- Camera Display Area using ttk.Notebook ---
        self.camera_notebook = ttk.Notebook(self.top_paned, style='Content.TNotebook')
        # Add custom style for notebook if needed, e.g., tab colors
        style.configure('Content.TNotebook', background=COLOR_FRAME_BG)
        style.configure('Content.TNotebook.Tab', background=COLOR_FRAME_BG, padding=[5, 2])
        style.map('Content.TNotebook.Tab', 
                  background=[('selected', COLOR_BACKGROUND), ('active', COLOR_FRAME_BG)],
                  foreground=[('selected', COLOR_PRIMARY_ACCENT)])

        self.heatmap_views = [] # Store references to all heatmap views
        self._populate_camera_tabs()

        self.trend_graph = TrendGraph(main_content_frame, set_status=status_update_method, style='Content.TFrame')
        
        # --- Wiring TrendGraph --- 
        # Option 1: Link trend graph to the first camera if available
        if self.heatmap_views: # If at least one heatmap view was created
            self.heatmap_views[0].trend_graph = self.trend_graph 
            # The HeatmapView.update_image() method pushes data to its self.trend_graph
            # This means only the first camera's data will go to the trend graph with current HeatmapView logic.
            # This will need to be made more dynamic if user can select which camera feeds the graph.
        else:
            # If no cameras, trend graph won't get data automatically from a heatmap view.
            # It could still be used for loading data or other purposes.
            pass 

        self.top_paned.add(self.control_panel, weight=1) # Control panel gets 1 part
        self.top_paned.add(self.camera_notebook, weight=2) # Camera notebook gets 2 parts

        self.trend_graph.grid(row=2, column=0, sticky='nsew')

        main_content_frame.columnconfigure(0, weight=1)
        main_content_frame.rowconfigure(0, weight=0)  # Status bar - no vertical expansion
        main_content_frame.rowconfigure(1, weight=3)  # Paned window (CP + Heatmap)
        main_content_frame.rowconfigure(2, weight=2)  # Trend graph

        # Set initial PanedWindow sash position after widgets are drawn
        self.after(100, self.set_initial_pane_proportions)
        
        # Configure trend graph export to use sample name from heatmap view
        self.trend_graph.export_btn.configure(command=self._export_trend_data_coordinated)

        # --- Start hotplug monitor ---
        self.camera_manager.start_hotplug_monitor(on_change=self._on_camera_hotplug)

        # --- Start PID output loop ---
        pid_sample_ms = max(10, int(self.pid.sample_time * 1000)) # Ensure minimum delay
        self.after(pid_sample_ms, self._update_pid_output)

        self.last_pid_output_time = 0 # To avoid updating siggen too frequently if sample_time is very small

    def _populate_camera_tabs(self):
        # Remove all tabs
        for tab in self.camera_notebook.tabs():
            self.camera_notebook.forget(tab)
        self.heatmap_views.clear()
        active_cameras = self.camera_manager.get_all_cameras()
        if not active_cameras:
            no_cam_frame = ttk.Frame(self.camera_notebook, style='Content.TFrame')
            msg_label = ttk.Label(no_cam_frame, text="No cameras available or started.", style='Content.TLabel', font=('Segoe UI', 12))
            msg_label.pack(padx=20, pady=20, expand=True, anchor='center')
            self.camera_notebook.add(no_cam_frame, text="No Cameras")
        else:
            for i, cam_instance in enumerate(active_cameras):
                tab_frame = ttk.Frame(self.camera_notebook, style='Content.TFrame')
                heatmap_view_instance = HeatmapView(
                    tab_frame,
                    camera=cam_instance,
                    trend_graph=None,
                    set_status=self.status_bar_view.set_status,
                    style='Content.TFrame'
                )
                heatmap_view_instance.pack(fill='both', expand=True)
                self.heatmap_views.append(heatmap_view_instance)
                tab_title = f"Camera {cam_instance.connected_port or f'ID-{i}'}"
                self.camera_notebook.add(tab_frame, text=tab_title)

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
            # Potentially get sample name from the currently selected tab's heatmap view
            try:
                selected_tab_index = self.camera_notebook.index(self.camera_notebook.select())
                if 0 <= selected_tab_index < len(self.heatmap_views):
                    sample_name = self.heatmap_views[selected_tab_index].get_sample_number()
                else: # Fallback to first if selection is weird
                    sample_name = self.heatmap_views[0].get_sample_number()
            except tk.TclError: # If no tab is selected or notebook is empty
                 if self.heatmap_views: # Fallback to first if any exist
                    sample_name = self.heatmap_views[0].get_sample_number()
        
        if hasattr(self, 'trend_graph') and self.trend_graph:
            self.trend_graph.export_csv(sample_name=sample_name) 

    def refresh_camera_tabs(self):
        # This method can be safely called from the hotplug thread using after()
        self.after(0, self._populate_camera_tabs)
        # Optionally, update trend graph linkage, etc.
        # You may want to re-link trend graph to the first available camera
        # or keep the previous selection if possible.

    def _on_camera_hotplug(self):
        print("SenxorApp: Camera hotplug event detected. Refreshing camera tabs...")
        self.refresh_camera_tabs() 

    def _update_pid_output(self):
        """Periodically calculates PID output and applies it to the signal generator."""
        if not self.pid: # Safety check
            return 

        reschedule_delay_ms = max(10, int(self.pid.sample_time * 1000))

        try:
            if self.pid.auto_mode:
                # Calculate PID output (must be called to update PID state)
                voltage = self.pid() 

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