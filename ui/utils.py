import tkinter as tk
from tkinter import ttk # Import ttk

# Robust tooltip helper for Tkinter/ttk widgets
class Tooltip:
    # Class variable to store the style name for the tooltip label
    _tooltip_style_name = None

    @staticmethod
    def configure_style(style_engine, style_name, **kwargs):
        '''Configures the ttk style for the tooltip's label.
           style_engine: The ttk.Style() instance.
           style_name: The name for this style (e.g., "App.Tooltip").
           **kwargs: Configuration options for ttk.Label (background, foreground, font, etc.)
        '''
        style_engine.configure(style_name, **kwargs)
        Tooltip._tooltip_style_name = style_name

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        # Bindings to show/hide/move tooltip
        widget.bind("<Enter>", self.enter, add='+')
        widget.bind("<Leave>", self.leave, add='+')
        widget.bind("<Motion>", self.motion, add='+')
        # Binding for when widget is destroyed
        widget.bind("<Destroy>", self.leave, add='+')


    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def motion(self, event):
        # Update position based on mouse movement ONLY if tip is visible
        if self.tipwindow:
            # For Tkinter root/toplevel, event.x_root, event.y_root are screen coords
            # For widgets within a Toplevel/Frame, event.x, event.y are relative to widget
            # We need consistent screen coordinates
            new_x = self.widget.winfo_rootx() + event.x + 20
            new_y = self.widget.winfo_rooty() + event.y + 10
            self.tipwindow.wm_geometry(f"+{new_x}+{new_y}")


    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.showtip) # 0.5 second delay

    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def showtip(self):
        if self.tipwindow or not self.text:
            return

        # Use widget's current position to initially place the tooltip
        # This handles cases where the mouse might not have moved yet over the widget
        # Fallback to last known mouse coordinates if needed
        try:
            # Get widget's top-left corner relative to screen
            base_x = self.widget.winfo_rootx()
            base_y = self.widget.winfo_rooty()
            # Approximate position: near the widget, slightly offset
            # self.x, self.y are updated by motion events if they occur
            current_x = base_x + self.widget.winfo_width() // 2
            current_y = base_y + self.widget.winfo_height() + 5 # Below the widget
            if self.x != 0 and self.y != 0: # if motion has occurred use that
                 current_x = self.x
                 current_y = self.y
            else: # if no motion, use widget position to guess
                 current_x = self.widget.winfo_rootx() + 20
                 current_y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5


        except tk.TclError: # Widget might not be mapped yet
            return

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1) # Remove window decorations
        
        # Default position (updated by motion if mouse moves over widget)
        tw.wm_geometry(f"+{current_x}+{current_y}")

        # Use ttk.Label for theming. Apply the configured style if available.
        if Tooltip._tooltip_style_name:
            label = ttk.Label(tw, text=self.text, justify='left', style=Tooltip._tooltip_style_name)
        else:
            # Fallback to a default tk.Label if style not configured (should not happen if app.py calls configure_style)
            label = tk.Label(
                tw, text=self.text, justify='left',
                background="#ffffe0", relief='solid', borderwidth=1,
                font=("Segoe UI", 9)
            )
        label.pack(ipadx=4, ipady=2)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy() 