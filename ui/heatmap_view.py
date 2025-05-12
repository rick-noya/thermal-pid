import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import cv2 as cv
from collections import deque
from .utils import Tooltip

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
    def __init__(self, master, camera, trend_graph=None, set_status=None, style='Content.TFrame', show_controls=True, colormap_var=None, hot_smooth_len_var=None, cold_smooth_len_var=None, **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.camera = camera
        self.trend_graph = trend_graph
        self.set_status = set_status or (lambda msg: None)
        
        # Desired fixed display size (may be set by parent container)
        self.target_size = (400, 310)  # Will be overwritten later if needed

        # Aspect ratio constants (sensor native 80x62)
        self.AR_W = 80
        self.AR_H = 62
        
        self.img_label = ttk.Label(self) # No specific style, will inherit from parent or default TFrame
        self.img_label.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.last_frame = None
        # self.last_overlay = None # Not used
        self.last_size = self.target_size
        self.after_id = None
        self.update_interval = 100  # ms (10 FPS)
        self.running = True
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Controls frame (optional) ---
        self.controls_frame = ttk.Frame(self, style='Content.TFrame', padding=(5,5))
        if show_controls:
            self.controls_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)

        # Configure columns for even spacing of control groups (only if visible)
        if show_controls:
            self.controls_frame.columnconfigure(0, weight=1) # Smoothing label + slider group 1
            self.controls_frame.columnconfigure(1, weight=1) # Smoothing label + slider group 2
            self.controls_frame.columnconfigure(2, weight=0) # Sample Number (less weight, fixed size)
            self.controls_frame.columnconfigure(3, weight=1) # Colormap label + optionmenu
            self.controls_frame.columnconfigure(4, weight=1) # Snapshot button

        self.img_label.bind('<Configure>', self.on_img_label_resize)
        Tooltip(self.img_label, "Live thermal image. Drag the window divider to resize.")

        # Use global variables if provided
        self.colormap_var = colormap_var
        self.hot_smooth_len_var = hot_smooth_len_var
        self.cold_smooth_len_var = cold_smooth_len_var

        # Hot/cold position history (deque for last N)
        self.hot_history = deque(maxlen=10)
        self.cold_history = deque(maxlen=10)

        self._create_disconnected_placeholder() # Create placeholder once
        self.update_image()

    def _create_disconnected_placeholder(self):
        # Create a placeholder image for when the camera is disconnected
        ph_width = self.last_size[0] if self.last_size[0] > 50 else 400
        ph_height = self.last_size[1] if self.last_size[1] > 50 else 310
        # Ensure width and height are positive for np.zeros
        ph_width = max(1, ph_width)
        ph_height = max(1, ph_height)
        
        img = np.zeros((ph_height, ph_width, 3), dtype=np.uint8) # Black image
        msg = "Camera Disconnected"
        font = cv.FONT_HERSHEY_SIMPLEX
        
        # Calculate text size and position carefully
        try:
            text_size = cv.getTextSize(msg, font, 1, 2)[0]
            text_x = (img.shape[1] - text_size[0]) // 2
            text_y = (img.shape[0] + text_size[1]) // 2
            # Ensure text coordinates are positive
            text_x = max(0, text_x)
            text_y = max(0, text_y)
            cv.putText(img, msg, (text_x, text_y), font, 1, (255, 255, 255), 2)
        except Exception as e:
            print(f"Error creating placeholder text: {e}") # Log error

        img_pil = Image.fromarray(img)
        self.disconnected_img_tk = ImageTk.PhotoImage(img_pil)

    def _show_disconnected_placeholder(self):
        # Update placeholder if size changed
        current_w, current_h = self.img_label.winfo_width(), self.img_label.winfo_height()
        # Check if winfo_width/height are valid (usually > 0 after window is shown)
        if current_w > 1 and current_h > 1 and (self.last_size[0] != current_w or self.last_size[1] != current_h):
            self.last_size = (current_w, current_h)
            self._create_disconnected_placeholder() # Recreate with current size
        
        self.img_label.imgtk = self.disconnected_img_tk
        self.img_label.configure(image=self.disconnected_img_tk)
        self.last_frame = None # Clear last valid frame

    def get_sample_number(self) -> str:
        return self.sample_number_var.get().strip()

    def on_img_label_resize(self, event):
        """Maintain 80x62 aspect ratio when the containing widget is resized."""
        w_avail, h_avail = event.width, event.height

        if w_avail < 10 or h_avail < 10:
            return

        # Determine the maximum size that fits in the available box while preserving AR
        aspect_ratio = self.AR_W / self.AR_H  # ~1.29 (w/h)

        calc_h = int(w_avail / aspect_ratio)
        calc_w = int(h_avail * aspect_ratio)

        if calc_h <= h_avail:
            new_w, new_h = w_avail, calc_h
        else:
            new_w, new_h = calc_w, h_avail

        # If size did not change, nothing to do
        if new_w == self.last_size[0] and new_h == self.last_size[1]:
            return

        self.last_size = (new_w, new_h)
        self._create_disconnected_placeholder()

        if self.last_frame is not None:
            self.render_frame(self.last_frame, size=self.last_size)
        elif not self.camera.is_connected:
            self._show_disconnected_placeholder()

    def update_image(self):
        if not self.running:
            return

        # self.camera is an instance of SenxorCamera passed during __init__
        if not self.camera or not hasattr(self.camera, 'is_connected'): # Basic check for valid camera object
            if self.set_status: self.set_status("HeatmapView: Invalid camera object.")
            self._show_disconnected_placeholder() # Show placeholder
            self.after_id = self.after(self.update_interval * 10, self.update_image) # Check much less frequently
            return

        if not self.camera.is_connected:
            self._show_disconnected_placeholder()
            if self.set_status:
                status_msg = f"Camera {self.camera.connected_port or self.camera._port or '(Unknown)'} not connected."
                self.set_status(status_msg)
            self.after_id = self.after(self.update_interval * 5, self.update_image)
            return
        
        if not self.camera.is_streaming: # Check if the camera's software streaming loop is active
            # This might happen if it was connected but streaming hasn't been started or was stopped.
            # CameraManager should ideally ensure only streaming cameras are passed or handled.
            # However, good to have a check here.
            self._show_disconnected_placeholder()
            if self.set_status:
                status_msg = f"Camera {self.camera.connected_port or '(ID)'} connected but not streaming. Waiting..."
                self.set_status(status_msg)
            self.after_id = self.after(self.update_interval * 2, self.update_image) # Check a bit sooner
            return

        # Use the new method for threaded acquisition
        frame, header = self.camera.get_latest_frame_and_header()
        
        if frame is not None:
            # Successfully read a frame
            if hasattr(self, 'disconnected_img_tk') and self.img_label.cget('image') == str(self.disconnected_img_tk):
                # If we were showing placeholder, clear it by rendering the new frame
                pass # The normal render_frame path will replace the placeholder
            
            if self.set_status:
                 # Clear potential previous "disconnected" or "error" message
                status_msg = "Streaming..."
                if header and 'frame_counter' in header:
                    status_msg = f"Frame {header['frame_counter']}"
                elif header and 'timestamp' in header: # Example of another header key
                    status_msg = f"Frame @ {header['timestamp']}"
                self.set_status(status_msg)

            self.last_frame = frame.copy()
            self.render_frame(frame, size=self.last_size)
            
            # Push data to trend graph
            min_temp = np.min(frame)
            max_temp = np.max(frame)
            avg_temp = np.mean(frame)
            # if self.trend_graph:
            #     current_voltage = 0.0 # Placeholder
            #     self.trend_graph.add_point(max_temp, min_temp, avg_temp, current_voltage)
            
            # Schedule next normal update
            self.after_id = self.after(self.update_interval, self.update_image)

        else: 
            # Frame is None. Camera.is_connected was true, so this is a read error.
            self._show_disconnected_placeholder() # Show placeholder on error too
            if self.set_status:
                self.set_status("Error reading frame from camera. Retrying...")
            # Schedule next attempt
            self.after_id = self.after(self.update_interval, self.update_image) 

    def render_frame(self, frame, size=(400, 310)):
        if frame is None: # Safeguard
            # This should ideally not be hit if update_image is correctly handling None frames
            if self.camera.is_connected:
                # If camera is supposed to be connected, but frame is None, show error placeholder
                if self.set_status: self.set_status("Render error: Frame is None.")
            self._show_disconnected_placeholder() 
            return
        
        # Ensure frame is not empty and is a numpy array before processing
        if not isinstance(frame, np.ndarray) or frame.size == 0:
            if self.set_status: self.set_status("Render error: Invalid frame data.")
            self._show_disconnected_placeholder() # Show placeholder for invalid data
            return
            
        min_temp = np.min(frame)
        max_temp = np.max(frame)
        # avg_temp = np.mean(frame) # Not used directly in this function
        frame_disp = np.clip(frame, min_temp, max_temp)
        norm = ((frame_disp - min_temp) / (max_temp - min_temp + 1e-6) * 255).astype(np.uint8)
        cmap_name = self.colormap_var.get()
        cmap_cv = COLORMAPS.get(cmap_name, cv.COLORMAP_VIRIDIS) # Default to Viridis if key error
        color_img = cv.applyColorMap(norm, cmap_cv)
        color_img = cv.resize(color_img, size, interpolation=cv.INTER_LINEAR) # INTER_LINEAR is faster
        
        show_hot = getattr(self, 'show_hot_spot_var', None)
        show_cold = getattr(self, 'show_cold_spot_var', None)
        show_hot = show_hot.get() if show_hot is not None else True
        show_cold = show_cold.get() if show_cold is not None else True
        # Hot/cold spot overlays
        if frame.size > 0: # Ensure frame is not empty
            scale_x = color_img.shape[1] / frame.shape[1]
            scale_y = color_img.shape[0] / frame.shape[0]
            min_loc_flat = np.argmin(frame)
            max_loc_flat = np.argmax(frame)
            if min_loc_flat is not None and max_loc_flat is not None:
                min_loc = np.unravel_index(min_loc_flat, frame.shape)
                max_loc = np.unravel_index(max_loc_flat, frame.shape)
                min_pixel = np.array([min_loc[1] * scale_x, min_loc[0] * scale_y])
                max_pixel = np.array([max_loc[1] * scale_x, max_loc[0] * scale_y])
                self.hot_history.append(max_pixel)
                self.cold_history.append(min_pixel)
                if show_hot and len(self.hot_history) > 0:
                    hot_avg = np.mean(self.hot_history, axis=0)
                    hot_pos = (int(hot_avg[0]), int(hot_avg[1]))
                    text_hot = f"{np.max(frame):.1f}0C"
                    font_face = cv.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    thickness_text = 1
                    thickness_outline = 2
                    text_color_fg = (255,255,255)
                    text_color_bg = (0,0,0)
                    (text_w, text_h), _ = cv.getTextSize(text_hot, font_face, font_scale, thickness_text)
                    text_org_hot = (hot_pos[0] + 10, hot_pos[1] - 10)
                    cv.putText(color_img, text_hot, text_org_hot, font_face, font_scale, text_color_bg, thickness_outline, cv.LINE_AA)
                    cv.putText(color_img, text_hot, text_org_hot, font_face, font_scale, text_color_fg, thickness_text, cv.LINE_AA)
                    cv.circle(color_img, hot_pos, 8, (0,0,255), 2)
                if show_cold and len(self.cold_history) > 0:
                    cold_avg = np.mean(self.cold_history, axis=0)
                    cool_pos = (int(cold_avg[0]), int(cold_avg[1]))
                    text_cold = f"{np.min(frame):.1f}C"
                    text_org_cold = (cool_pos[0] + 10, cool_pos[1] - 10)
                    cv.putText(color_img, text_cold, text_org_cold, font_face, font_scale, text_color_bg, thickness_outline, cv.LINE_AA)
                    cv.putText(color_img, text_cold, text_org_cold, font_face, font_scale, text_color_fg, thickness_text, cv.LINE_AA)
                    cv.circle(color_img, cool_pos, 8, (255,0,0), 2)

        img_rgb = cv.cvtColor(color_img, cv.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.img_label.imgtk = img_tk
        self.img_label.configure(image=img_tk)

    def stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id) 

    # --- External helper to enforce a fixed target size ---
    def set_target_size(self, width: int, height: int):
        """Set a desired display size for the heatmap image (maintains aspect ratio internally)."""
        # Adjust to maintain internal AR strictly
        aspect_ratio = self.AR_W / self.AR_H
        height_from_w = int(width / aspect_ratio)
        width_from_h = int(height * aspect_ratio)

        # Choose the smaller constraint to avoid stretching
        if height_from_w <= height:
            self.last_size = (max(1,width), max(1,height_from_w))
        else:
            self.last_size = (max(1,width_from_h), max(1,height))

        # Trigger a re-render or placeholder update with new size
        self._create_disconnected_placeholder()
        if self.last_frame is not None:
            self.render_frame(self.last_frame, size=self.last_size)
        elif not self.camera.is_connected:
            self._show_disconnected_placeholder() 

    # Rotate button
    # if show_controls:
    #     self.rotate_btn = ttk.Button(self.controls_frame, text="⟳ Rotate", command=self.rotate_view)
    #     self.rotate_btn.grid(row=0, column=5, padx=5, pady=2, sticky='e')
    #     Tooltip(self.rotate_btn, "Rotate the camera view 90° clockwise.")

    # --- Apply rotation ---
    # def rotate_point(pt, shape, rotation):
    #     h, w = shape[:2]
    #     x, y = pt
    #     if rotation == 90:
    #         return (h - 1 - y, x)
    #     elif rotation == 180:
    #         return (w - 1 - x, h - 1 - y)
    #     elif rotation == 270:
    #         return (y, w - 1 - x)
    #     else:
    #         return (x, y)
    #
    # if self.rotation == 90:
    #     color_img = cv.rotate(color_img, cv.ROTATE_90_CLOCKWISE)
    # elif self.rotation == 180:
    #     color_img = cv.rotate(color_img, cv.ROTATE_180)
    # elif self.rotation == 270:
    #     color_img = cv.rotate(color_img, cv.ROTATE_90_COUNTERCLOCKWISE)
    #
    #     # Rotate overlay points to match image rotation
    #     min_pixel_rot = rotate_point(min_pixel, color_img.shape, self.rotation)
    #     max_pixel_rot = rotate_point(max_pixel, color_img.shape, self.rotation)
    #     self.hot_history.append(max_pixel_rot)
    #     self.cold_history.append(min_pixel_rot)
    #
    # if self.rotation == 90:
    #     color_img = cv.rotate(color_img, cv.ROTATE_90_CLOCKWISE)
    # elif self.rotation == 180:
    #     color_img = cv.rotate(color_img, cv.ROTATE_180)
    # elif self.rotation == 270:
    #     color_img = cv.rotate(color_img, cv.ROTATE_90_COUNTERCLOCKWISE)
    #
    #     # Rotate overlay points to match image rotation
    #     min_pixel_rot = rotate_point(min_pixel, color_img.shape, self.rotation)
    #     max_pixel_rot = rotate_point(max_pixel, color_img.shape, self.rotation)
    #     self.hot_history.append(max_pixel_rot)
    #     self.cold_history.append(min_pixel_rot)

    # def rotate_view(self):
    #     """Rotate the camera view by 90 degrees clockwise."""
    #     self.rotation = (self.rotation + 90) % 360
    #     if self.last_frame is not None:
    #         self.render_frame(self.last_frame, size=self.last_size) 