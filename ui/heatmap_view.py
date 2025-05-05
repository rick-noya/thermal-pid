import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import cv2 as cv

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
        ttk.Label(controls, text="Cold Smoothing:").grid(row=0, column=2, sticky='e')
        self.cold_smooth_var = tk.DoubleVar(value=0.2)
        cold_slider = ttk.Scale(controls, from_=0.01, to=0.5, variable=self.cold_smooth_var, orient='horizontal', length=100)
        cold_slider.grid(row=0, column=3, sticky='ew', padx=2)

        # Colormap selector
        ttk.Label(controls, text="Colormap:").grid(row=0, column=4, sticky='e')
        self.colormap_var = tk.StringVar(value='Jet')
        colormap_menu = ttk.OptionMenu(controls, self.colormap_var, 'Jet', *COLORMAPS.keys())
        colormap_menu.grid(row=0, column=5, sticky='ew', padx=2)

        # Snapshot button
        self.snapshot_btn = ttk.Button(controls, text="Save Snapshot", command=self.save_snapshot)
        self.snapshot_btn.grid(row=0, column=6, padx=8, sticky='ew')

        # Smoothing state
        self.hot_avg = None
        self.cool_avg = None

        self.img_label.bind('<Configure>', self.on_img_label_resize)
        self.update_image()

    def on_img_label_resize(self, event):
        # Redraw the last frame at the new size
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
        # Smoothing
        hot_alpha = self.hot_smooth_var.get()
        cold_alpha = self.cold_smooth_var.get()
        if self.hot_avg is None:
            self.hot_avg = max_pixel.copy()
        else:
            self.hot_avg = (1 - hot_alpha) * self.hot_avg + hot_alpha * max_pixel
        if self.cool_avg is None:
            self.cool_avg = min_pixel.copy()
        else:
            self.cool_avg = (1 - cold_alpha) * self.cool_avg + cold_alpha * min_pixel
        hot_pos = (int(self.hot_avg[0]), int(self.hot_avg[1]))
        cool_pos = (int(self.cool_avg[0]), int(self.cool_avg[1]))
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