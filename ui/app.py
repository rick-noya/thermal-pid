import tkinter as tk
from tkinter import ttk
from .control_panel import ControlPanel
from .heatmap_view import HeatmapView
from .trend_graph import TrendGraph

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

        # Modern theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#f5f7fa')
        style.configure('TLabel', background='#f5f7fa', font=('Segoe UI', 11))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'), padding=6)
        style.configure('TCheckbutton', background='#f5f7fa', font=('Segoe UI', 10))
        style.configure('TLabelframe', background='#e3eaf2', font=('Segoe UI', 12, 'bold'))
        style.configure('TLabelframe.Label', background='#e3eaf2', font=('Segoe UI', 12, 'bold'))

        # Top row: PanedWindow for control panel and heatmap view
        self.top_paned = ttk.PanedWindow(self, orient='horizontal')
        self.top_paned.grid(row=0, column=0, columnspan=2, sticky='nsew', padx=0, pady=0)

        self.control_panel = ControlPanel(self.top_paned, pid, siggen, set_status=self.set_status)
        self.heatmap_view = HeatmapView(self.top_paned, camera, trend_graph=None, set_status=self.set_status)
        self.trend_graph = TrendGraph(self, set_status=self.set_status)
        self.heatmap_view.trend_graph = self.trend_graph  # wire up after creation

        self.top_paned.add(self.control_panel)
        self.top_paned.add(self.heatmap_view)

        # Bottom row: graph
        self.trend_graph.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=10, pady=(0,10))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=2)
        self.rowconfigure(1, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief='sunken', anchor='w', font=('Segoe UI', 10))
        status_bar.grid(row=2, column=0, columnspan=2, sticky='ew', padx=2, pady=(0,4))

        # Set initial PanedWindow sash position after widgets are drawn
        self.after(100, self.set_initial_pane_proportions)

    def set_initial_pane_proportions(self):
        self.update_idletasks()
        total = self.top_paned.winfo_width()
        # Set sash so control panel is about 60% and heatmap 40%
        self.top_paned.sashpos(0, int(total * 0.6))

    def set_status(self, msg):
        self.status_var.set(msg) 