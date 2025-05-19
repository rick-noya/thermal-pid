import tkinter as tk
from tkinter import ttk

class StatusControls(ttk.Frame):
    """
    UI component for status display and update logic.
    Encapsulates phase/status variables and update methods.
    """
    def __init__(self, master, initial_phase="Idle", **kwargs):
        super().__init__(master, **kwargs)
        self.phase_var = tk.StringVar(value=initial_phase)
        self.status_var = tk.StringVar(value="Ready.")

        # Phase label
        self.phase_label = ttk.Label(self, textvariable=self.phase_var, style='Content.TLabel')
        self.phase_label.grid(row=0, column=0, sticky='w', padx=5, pady=2)

        # Status bar
        self.status_label = ttk.Label(self, textvariable=self.status_var, style='Status.TLabel', anchor='w', relief='flat', padding=(3,2))
        self.status_label.grid(row=1, column=0, sticky='ew', padx=5, pady=(5,2))
        self.columnconfigure(0, weight=1)

    def set_phase(self, phase):
        self.phase_var.set(phase)

    def set_status(self, status):
        self.status_var.set(status) 