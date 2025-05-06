import tkinter as tk
from tkinter import ttk
from .control_panel import ControlPanel
from .heatmap_view import HeatmapView
from .trend_graph import TrendGraph
from .utils import Tooltip # Import Tooltip to style it here

class SenxorApp(ttk.Frame):
    def __init__(self, master, camera, siggen, pid):
        super().__init__(master)
        self.master = master
        self.camera = camera
        self.siggen = siggen
        self.pid = pid
        self.pack(fill='both', expand=True)

        # Set default window size
        self.master.geometry('1300x750')
        self.master.title("Senxor Thermal Control & Analysis")

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
        style.configure('Status.TLabel', background=COLOR_BACKGROUND, font=('Segoe UI', 9), foreground=COLOR_TEXT_LIGHT)

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
        # Using a more descriptive style for frames that contain actual content
        main_content_frame = ttk.Frame(self, style='Content.TFrame')
        main_content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Top row: PanedWindow for control panel and heatmap view
        self.top_paned = ttk.PanedWindow(main_content_frame, orient='horizontal')
        self.top_paned.grid(row=0, column=0, sticky='nsew', pady=(0,10))

        # Pass the Content.TFrame style to internal frames of ControlPanel if needed, or let them inherit
        self.control_panel = ControlPanel(self.top_paned, pid, siggen, set_status=self.set_status, style='Content.TFrame')
        self.heatmap_view = HeatmapView(self.top_paned, camera, trend_graph=None, set_status=self.set_status, style='Content.TFrame')
        # TrendGraph is also a content frame
        self.trend_graph = TrendGraph(main_content_frame, set_status=self.set_status, style='Content.TFrame')
        self.heatmap_view.trend_graph = self.trend_graph  # wire up after creation

        self.top_paned.add(self.control_panel, weight=3) # Give CP a bit more initial space ~60%
        self.top_paned.add(self.heatmap_view, weight=2) # ~40%

        # Bottom row: graph
        self.trend_graph.grid(row=1, column=0, sticky='nsew')

        main_content_frame.columnconfigure(0, weight=1)
        main_content_frame.rowconfigure(0, weight=3) # Heatmap and controls take more space
        main_content_frame.rowconfigure(1, weight=2) # Trend graph takes less

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief='flat', anchor='w', style='Status.TLabel', padding=(5,3))
        status_bar.pack(side='bottom', fill='x')

        # Set initial PanedWindow sash position after widgets are drawn
        self.after(100, self.set_initial_pane_proportions)

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
        self.status_var.set(msg) 