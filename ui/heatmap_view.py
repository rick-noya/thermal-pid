import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import cv2 as cv
from collections import deque

COLORMAPS = {
    'Jet': cv.COLORMAP_JET,
    'Hot': cv.COLORMAP_HOT,
    'Magma': cv.COLORMAP_MAGMA,
    'Inferno': cv.COLORMAP_INFERNO,
    'Plasma': cv.COLORMAP_PLASMA,
    'Viridis': cv.COLORMAP_VIRIDIS,
    'Cividis': cv.COLORMAP_CIVIDIS,
    'Twilight': cv.COLORMAP_TWILIGHT,
    'Turbo': cv.COLORMAP_TURBO,
}

# Simple tooltip helper for Tkinter widgets
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
    def show(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0,0,0,0)
        x = x + self.widget.winfo_rootx() + 20
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(1)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify='left', background="#ffffe0", relief='solid', borderwidth=1, font=("Segoe UI", 9))
        label.pack(ipadx=4, ipady=2)
    def hide(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

class HeatmapView(ttk.Frame):
    def __init__(self, master, camera, trend_graph=None, set_status=None, **kwargs):
        super().__init__(master, **kwargs)
        self.camera = camera
        self.trend_graph = trend_graph
        self.set_status = set_status or (lambda msg: None)
        self.img_label = ttk.Label(self)
        self.img_label.grid(row=0, column=0, padx=8, pady=(8,2), sticky='nsew')
        self.last_frame = None
        self.last_overlay = None
        self.last_size = (400, 310)
        self.after_id = None
        self.update_interval = 100  # ms
        self.running = True
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Controls frame ---
        controls = ttk.Frame(self)
        controls.grid(row=1, column=0, sticky='ew', padx=8, pady=(2,8))
        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(2, weight=1)
        controls.columnconfigure(3, weight=1)
        controls.columnconfigure(4, weight=1)

        # Smoothing controls
        ttk.Label(controls, text="Hot Smoothing:").grid(row=0, column=0, sticky='e')
        self.hot_smooth_var = tk.DoubleVar(value=0.2)
        hot_slider = ttk.Scale(controls, from_=0.01, to=0.5, variable=self.hot_smooth_var, orient='horizontal', length=100)
        hot_slider.grid(row=0, column=1, sticky='ew', padx=2)
        Tooltip(hot_slider, "Adjusts how much the hot spot overlay is smoothed over time.")
        ttk.Label(controls, text="Cold Smoothing:").grid(row=0, column=2, sticky='e')
        self.cold_smooth_var = tk.DoubleVar(value=0.2)
        cold_slider = ttk.Scale(controls, from_=0.01, to=0.5, variable=self.cold_smooth_var, orient='horizontal', length=100)
        cold_slider.grid(row=0, column=3, sticky='ew', padx=2)
        Tooltip(cold_slider, "Adjusts how much the cold spot overlay is smoothed over time.")

        # Colormap selector
        ttk.Label(controls, text="Colormap:").grid(row=0, column=4, sticky='e')
        self.colormap_var = tk.StringVar(value='Jet')
        colormap_menu = ttk.OptionMenu(controls, self.colormap_var, 'Jet', *COLORMAPS.keys())
        colormap_menu.grid(row=0, column=5, sticky='ew', padx=2)
        Tooltip(colormap_menu, "Select the color palette for the heatmap display.")

        # Snapshot button
        self.snapshot_btn = ttk.Button(controls, text="Save Snapshot", command=self.save_snapshot)
        self.snapshot_btn.grid(row=0, column=6, padx=8, sticky='ew')
        Tooltip(self.snapshot_btn, "Save the current frame as a CSV file.")

        # Hot/cold position history (deque for last 10)
        self.hot_history = deque(maxlen=10)
        self.cold_history = deque(maxlen=10)

        self.img_label.bind('<Configure>', self.on_img_label_resize)
        Tooltip(self.img_label, "Live thermal image with hot/cold overlays. Drag the divider to resize.")
        self.update_image()

    def on_img_label_resize(self, event):
        w, h = event.width, event.height
        if w < 50 or h < 50:
            return
        self.last_size = (w, h)
        if self.last_frame is not None:
            self.render_frame(self.last_frame, size=(w, h))

    def update_image(self):
        if not self.running:
            return
        frame, header = self.camera.read_frame()
        if frame is not None:
            self.last_frame = frame.copy()
            self.render_frame(frame, size=self.last_size)
            # Push data to trend graph
            min_temp = np.min(frame)
            max_temp = np.max(frame)
            avg_temp = np.mean(frame)
            if self.trend_graph is not None:
                self.trend_graph.add_point(max_temp, min_temp, avg_temp)
        self.after_id = self.after(self.update_interval, self.update_image)

    def render_frame(self, frame, size=(400, 310)):
        min_temp = np.min(frame)
        max_temp = np.max(frame)
        avg_temp = np.mean(frame)
        frame_disp = np.clip(frame, min_temp, max_temp)
        norm = ((frame_disp - min_temp) / (max_temp - min_temp + 1e-6) * 255).astype(np.uint8)
        cmap = COLORMAPS.get(self.colormap_var.get(), cv.COLORMAP_JET)
        color = cv.applyColorMap(norm, cmap)
        color = cv.resize(color, size, interpolation=cv.INTER_CUBIC)
        # Hot/cold spot overlays
        scale_x = color.shape[1] / frame.shape[1]
        scale_y = color.shape[0] / frame.shape[0]
        min_loc = np.unravel_index(np.argmin(frame), frame.shape)
        max_loc = np.unravel_index(np.argmax(frame), frame.shape)
        min_pixel = np.array([min_loc[1] * scale_x, min_loc[0] * scale_y])
        max_pixel = np.array([max_loc[1] * scale_x, max_loc[0] * scale_y])
        # Update history
        self.hot_history.append(max_pixel)
        self.cold_history.append(min_pixel)
        # Use average of last 10
        hot_avg = np.mean(self.hot_history, axis=0)
        cold_avg = np.mean(self.cold_history, axis=0)
        hot_pos = (int(hot_avg[0]), int(hot_avg[1]))
        cool_pos = (int(cold_avg[0]), int(cold_avg[1]))
        # Draw overlays
        cv.circle(color, hot_pos, 8, (0,0,255), 2)
        cv.putText(color, f"{np.max(frame):.1f}C", (hot_pos[0]+10, hot_pos[1]-10), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
        cv.circle(color, cool_pos, 8, (255,0,0), 2)
        cv.putText(color, f"{np.min(frame):.1f}C", (cool_pos[0]+10, cool_pos[1]-10), cv.FONT_HERSHEY_SIMPLEX, 0.7, (255,0,0), 2)
        img_rgb = cv.cvtColor(color, cv.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.img_label.imgtk = img_tk
        self.img_label.configure(image=img_tk)

    def save_snapshot(self):
        if self.last_frame is not None:
            import time
            filename = f"snapshot_{time.strftime('%Y%m%d-%H%M%S')}.csv"
            np.savetxt(filename, self.last_frame, delimiter=",", fmt="%.2f")
            self.set_status(f"Snapshot saved to {filename}")
        else:
            self.set_status("No frame to save.")

    def stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id) 