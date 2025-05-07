import tkinter as tk
from tkinter import ttk
from .control_panel import ControlPanel
from .heatmap_view import HeatmapView
from .trend_graph import TrendGraph
from .oscilloscope_panel import OscilloscopePanel
from .utils import Tooltip
from .status_bar_view import StatusBarView # Import new StatusBarView

class SenxorApp(ttk.Frame):
    def __init__(self, master, camera, siggen, pid, osc):
        super().__init__(master)
        self.master = master
        self.camera = camera
        self.siggen = siggen
        self.pid = pid
        self.osc = osc
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
        
        # --- Style for Notebook (Tabs) ---
        style.configure('TNotebook', background=COLOR_BACKGROUND, borderwidth=0, tabmargins=[2, 5, 2, 0])
        style.configure('TNotebook.Tab', 
                        background=COLOR_FRAME_BG, 
                        foreground=COLOR_TEXT_LIGHT, 
                        padding=[10, 5], 
                        font=('Segoe UI', 10, 'bold'),
                        borderwidth=0)
        style.map('TNotebook.Tab',
                  background=[('selected', COLOR_BACKGROUND), ('!selected', COLOR_FRAME_BG), ('active', COLOR_BACKGROUND)],
                  foreground=[('selected', COLOR_PRIMARY_ACCENT), ('!selected', COLOR_TEXT_LIGHT), ('active', COLOR_PRIMARY_ACCENT)],
                  expand=[('selected', [1, 1, 1, 0])]) # Small top border for selected tab

        # Main layout panels
        # Using a more descriptive style for frames that contain actual content
        main_content_frame = ttk.Frame(self, style='Content.TFrame')
        main_content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Instantiate new StatusBarView (row 0 of main_content_frame)
        self.status_bar_view = StatusBarView(main_content_frame, style='TFrame') # Use TFrame for main app bg for status bar
        self.status_bar_view.grid(row=0, column=0, sticky='ew', pady=(0,5)) # pady to give some space below it

        # Pass the StatusBarView's set_status method to child components
        status_update_method = self.status_bar_view.set_status

        # Create a main horizontal PanedWindow
        self.main_horizontal_pane = ttk.PanedWindow(main_content_frame, orient='horizontal')
        self.main_horizontal_pane.grid(row=1, column=0, sticky='nsew')

        self.control_panel = ControlPanel(self.main_horizontal_pane, pid, siggen, set_status=status_update_method, style='Content.TFrame')
        
        # Create a Notebook for the right side views
        self.right_notebook = ttk.Notebook(self.main_horizontal_pane)

        self.heatmap_view = HeatmapView(self.right_notebook, camera, trend_graph=None, pid=self.pid, siggen=self.siggen, osc=self.osc, set_status=status_update_method, style='Content.TFrame')
        self.trend_graph = TrendGraph(self.right_notebook, set_status=status_update_method, style='Content.TFrame')
        self.heatmap_view.trend_graph = self.trend_graph  # wire up after creation
        self.osc_panel = OscilloscopePanel(self.right_notebook, self.osc, set_status=status_update_method, style='Content.TFrame')

        # Add control_panel to the left of the main horizontal pane
        self.main_horizontal_pane.add(self.control_panel, weight=1) # Adjust weight as needed, e.g., 30-35% for control panel

        # Add the right_notebook to the right of the main horizontal pane
        self.main_horizontal_pane.add(self.right_notebook, weight=3) # Adjust weight, e.g., 65-70% for the right stack

        # Add views as tabs to the notebook
        self.right_notebook.add(self.heatmap_view, text='Thermal Image')
        self.right_notebook.add(self.trend_graph, text='Trend Analysis')
        self.right_notebook.add(self.osc_panel, text='Oscilloscope')


        main_content_frame.columnconfigure(0, weight=1)
        main_content_frame.rowconfigure(0, weight=0)  # Status bar
        main_content_frame.rowconfigure(1, weight=1)  # Main content area (main_horizontal_pane)


        # Set initial PanedWindow sash position after widgets are drawn
        self.after(100, self.set_initial_pane_proportions)
        
        # Configure trend graph export to use sample name from heatmap view
        self.trend_graph.export_btn.configure(command=self._export_trend_data_coordinated)

    def set_initial_pane_proportions(self):
        self.update_idletasks()
        try:
            # Set sash for main_horizontal_pane
            total_w_main = self.main_horizontal_pane.winfo_width()
            if total_w_main > 0 and len(self.main_horizontal_pane.panes()) == 2:
                # Example: control_panel gets ~35% of width
                self.main_horizontal_pane.sashpos(0, int(total_w_main * 0.35))

            # No need to set sashes for the notebook content, it manages its children via tabs

        except tk.TclError: # Handles cases where widget might not be fully initialized
            self.after(100, self.set_initial_pane_proportions) # Retry

    def set_status(self, msg):
        if hasattr(self, 'status_bar_view') and self.status_bar_view: # Check if it exists
            self.status_bar_view.set_status(msg)
        else: # Fallback if called before status_bar_view is initialized (should not happen in normal flow)
            print(f"Status (early): {msg}")

    def _export_trend_data_coordinated(self):
        sample_name = ""
        if hasattr(self, 'heatmap_view') and self.heatmap_view:
            sample_name = self.heatmap_view.get_sample_number()
        
        if hasattr(self, 'trend_graph') and self.trend_graph:
            self.trend_graph.export_csv(sample_name=sample_name) 