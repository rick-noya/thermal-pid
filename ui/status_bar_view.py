import tkinter as tk
from tkinter import ttk

class StatusBarView(ttk.Frame):
    def __init__(self, master, style='TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        
        self.status_var = tk.StringVar(value="Application Ready.")
        # Assuming 'Status.TLabel' is defined in the main app's style configuration
        # and provides desired padding, font, etc.
        status_label = ttk.Label(self, textvariable=self.status_var, style='Status.TLabel', anchor='w', relief='flat')
        status_label.pack(side='left', fill='x', expand=True, padx=5, pady=2)

    def set_status(self, message: str):
        self.status_var.set(message)

    def get_status(self) -> str:
        return self.status_var.get() 