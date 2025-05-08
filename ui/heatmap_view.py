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
    def __init__(self, master, camera, trend_graph=None, set_status=None, style='Content.TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.camera = camera
        self.trend_graph = trend_graph
        self.set_status = set_status or (lambda msg: None)
        
        self.img_label = ttk.Label(self) # No specific style, will inherit from parent or default TFrame
        self.img_label.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.last_frame = None
        # self.last_overlay = None # Not used
        self.last_size = (400, 310) # Default, will be updated by configure
        self.after_id = None
        self.update_interval = 100  # ms (10 FPS)
        self.running = True
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Controls frame ---
        controls_frame = ttk.Frame(self, style='Content.TFrame', padding=(5,5))
        controls_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        # Configure columns for even spacing of control groups
        controls_frame.columnconfigure(0, weight=1) # Smoothing label + slider group 1
        controls_frame.columnconfigure(1, weight=1) # Smoothing label + slider group 2
        controls_frame.columnconfigure(2, weight=0) # Sample Number (less weight, fixed size)
        controls_frame.columnconfigure(3, weight=1) # Colormap label + optionmenu
        controls_frame.columnconfigure(4, weight=1) # Snapshot button

        # Smoothing controls group
        smoothing_group = ttk.Frame(controls_frame, style='Content.TFrame')
        smoothing_group.grid(row=0, column=0, columnspan=2, sticky='ew', padx=(0,10))
        smoothing_group.columnconfigure(1, weight=1) # Slider 1
        smoothing_group.columnconfigure(3, weight=1) # Slider 2

        ttk.Label(smoothing_group, text="Hot Spot Smooth (frames):", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=2, pady=2)
        self.hot_smooth_len_var = tk.IntVar(value=10)
        hot_slider = ttk.Scale(smoothing_group, from_=1, to=30, variable=self.hot_smooth_len_var, orient='horizontal', length=120, command=self.on_smooth_len_change)
        hot_slider.grid(row=0, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(hot_slider, "Number of frames to average for hot spot marker position (1-30).")
        # Display current value for slider
        self.hot_smooth_display = ttk.Label(smoothing_group, textvariable=self.hot_smooth_len_var, style='Content.TLabel', width=3)
        self.hot_smooth_display.grid(row=0, column=2, sticky='w', padx=2)

        ttk.Label(smoothing_group, text="Cold Spot Smooth (frames):", style='Content.TLabel').grid(row=1, column=0, sticky='w', padx=2, pady=2)
        self.cold_smooth_len_var = tk.IntVar(value=10)
        cold_slider = ttk.Scale(smoothing_group, from_=1, to=30, variable=self.cold_smooth_len_var, orient='horizontal', length=120, command=self.on_smooth_len_change)
        cold_slider.grid(row=1, column=1, sticky='ew', padx=5, pady=2)
        Tooltip(cold_slider, "Number of frames to average for cold spot marker position (1-30).")
        self.cold_smooth_display = ttk.Label(smoothing_group, textvariable=self.cold_smooth_len_var, style='Content.TLabel', width=3)
        self.cold_smooth_display.grid(row=1, column=2, sticky='w', padx=2)

        # Sample Number Input Group
        sample_info_group = ttk.Frame(controls_frame, style='Content.TFrame')
        sample_info_group.grid(row=0, column=2, sticky='ew', padx=5)
        sample_info_group.columnconfigure(1, weight=1) # Entry expands
        ttk.Label(sample_info_group, text="Sample #:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(5,2), pady=2)
        self.sample_number_var = tk.StringVar()
        sample_entry = ttk.Entry(sample_info_group, textvariable=self.sample_number_var, width=10)
        sample_entry.grid(row=0, column=1, sticky='ew', padx=(0,5), pady=2)
        Tooltip(sample_entry, "Enter the sample identifier for this test run.")

        # Colormap selector group
        colormap_group = ttk.Frame(controls_frame, style='Content.TFrame')
        colormap_group.grid(row=0, column=3, sticky='ew', padx=5) # Shifted to column 3
        colormap_group.columnconfigure(1, weight=1)
        ttk.Label(colormap_group, text="Colormap:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=2, pady=2)
        self.colormap_var = tk.StringVar(value='Viridis') # Changed default to Viridis
        colormap_menu = ttk.OptionMenu(colormap_group, self.colormap_var, self.colormap_var.get(), *COLORMAPS.keys())
        colormap_menu.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        Tooltip(colormap_menu, "Select the color palette for the heatmap display.")

        # Snapshot button
        self.snapshot_btn = ttk.Button(controls_frame, text="Save Snapshot", command=self.save_snapshot)
        self.snapshot_btn.grid(row=0, column=4, padx=10, pady=2, sticky='e') # Shifted to column 4
        Tooltip(self.snapshot_btn, "Save the current thermal data as a CSV file and image.")

        # Hot/cold position history (deque for last N)
        self.hot_history = deque(maxlen=self.hot_smooth_len_var.get())
        self.cold_history = deque(maxlen=self.cold_smooth_len_var.get())

        self.img_label.bind('<Configure>', self.on_img_label_resize)
        Tooltip(self.img_label, "Live thermal image. Drag the window divider to resize.")
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

    def on_smooth_len_change(self, value=None): # Value from scale is string, convert if needed
        # Recreate deques with new maxlen
        # It's important to handle potential partial data if deques are shortened
        # For simplicity, we just create new ones. Old history is lost on change.
        new_hot_len = self.hot_smooth_len_var.get()
        if new_hot_len < 1: new_hot_len = 1 # Ensure positive
        if not hasattr(self, 'hot_history') or self.hot_history.maxlen != new_hot_len:
            self.hot_history = deque(maxlen=new_hot_len)

        new_cold_len = self.cold_smooth_len_var.get()
        if new_cold_len < 1: new_cold_len = 1
        if not hasattr(self, 'cold_history') or self.cold_history.maxlen != new_cold_len:
            self.cold_history = deque(maxlen=new_cold_len)
        # self.set_status(f"Smoothing history set to: Hot {new_hot_len}, Cold {new_cold_len}")

    def on_img_label_resize(self, event):
        w, h = event.width, event.height
        if w < 10 or h < 10: # Reduced minimum size slightly
            return
        self.last_size = (w, h)
        self._create_disconnected_placeholder() # Re-create placeholder on resize to fit new size
        if self.last_frame is not None:
            self.render_frame(self.last_frame, size=(w, h))
        elif not self.camera.is_connected: # If camera is disconnected, show updated placeholder
            self._show_disconnected_placeholder()
        # If camera is connected but last_frame is None (e.g. initial state before first frame)
        # it will be handled by update_image subsequently.

    def update_image(self):
        if not self.running:
            return

        if not self.camera.is_connected:
            self._show_disconnected_placeholder()
            if self.set_status:
                # Using a slightly different message to distinguish from frame read error
                self.set_status("Camera not detected. Waiting for connection...") 
            # Try to update image again, maybe camera will be connected
            self.after_id = self.after(self.update_interval * 5, self.update_image) # Check less frequently
            return

        frame, header = self.camera.read_frame()
        
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
            if self.trend_graph:
                current_voltage = 0.0 # Placeholder
                self.trend_graph.add_point(max_temp, min_temp, avg_temp, current_voltage)
            
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
                
                if len(self.hot_history) > 0:
                    hot_avg = np.mean(self.hot_history, axis=0)
                    hot_pos = (int(hot_avg[0]), int(hot_avg[1]))
                    # Draw outlined text for hot spot
                    text_hot = f"{np.max(frame):.1f}0C"
                    font_face = cv.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.6
                    thickness_text = 1
                    thickness_outline = 2
                    text_color_fg = (255,255,255) # White
                    text_color_bg = (0,0,0)     # Black
                    (text_w, text_h), _ = cv.getTextSize(text_hot, font_face, font_scale, thickness_text)
                    text_org_hot = (hot_pos[0] + 10, hot_pos[1] - 10)
                    # Outline
                    cv.putText(color_img, text_hot, text_org_hot, font_face, font_scale, text_color_bg, thickness_outline, cv.LINE_AA)
                    # Foreground
                    cv.putText(color_img, text_hot, text_org_hot, font_face, font_scale, text_color_fg, thickness_text, cv.LINE_AA)
                    cv.circle(color_img, hot_pos, 8, (0,0,255), 2) # Red circle for hot

                if len(self.cold_history) > 0:
                    cold_avg = np.mean(self.cold_history, axis=0)
                    cool_pos = (int(cold_avg[0]), int(cold_avg[1]))
                    # Draw outlined text for cold spot
                    text_cold = f"{np.min(frame):.1f}C"
                    text_org_cold = (cool_pos[0] + 10, cool_pos[1] - 10)
                    # Outline
                    cv.putText(color_img, text_cold, text_org_cold, font_face, font_scale, text_color_bg, thickness_outline, cv.LINE_AA)
                    # Foreground
                    cv.putText(color_img, text_cold, text_org_cold, font_face, font_scale, text_color_fg, thickness_text, cv.LINE_AA)
                    cv.circle(color_img, cool_pos, 8, (255,0,0), 2) # Blue circle for cold

        img_rgb = cv.cvtColor(color_img, cv.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        self.img_label.imgtk = img_tk
        self.img_label.configure(image=img_tk)

    def save_snapshot(self):
        if self.last_frame is not None:
            import time
            timestamp = time.strftime('%Y%m%d-%H%M%S')
            sample_name = self.get_sample_number()
            
            if sample_name:
                base_filename = f"{sample_name}_snapshot_{timestamp}"
            else:
                base_filename = f"snapshot_{timestamp}"
            
            csv_filename = f"{base_filename}.csv"
            img_filename = f"{base_filename}.png"

            try:
                np.savetxt(csv_filename, self.last_frame, delimiter=",", fmt="%.2f")
                self.set_status(f"Snapshot data saved to {csv_filename}")
                
                # Save the current visual frame as well (the one with overlays)
                if hasattr(self.img_label, 'imgtk') and self.img_label.imgtk:
                    # We have the PhotoImage, try to get PIL Image from it
                    # This depends on how PhotoImage was created. If from PIL, it might have a reference.
                    # A more robust way: re-render the last frame to a PIL Image for saving.
                    
                    # Re-render for saving to ensure it's the latest with current colormap etc.
                    min_temp, max_temp = np.min(self.last_frame), np.max(self.last_frame)
                    norm_save = ((np.clip(self.last_frame, min_temp, max_temp) - min_temp) / (max_temp - min_temp + 1e-6) * 255).astype(np.uint8)
                    cmap_cv_save = COLORMAPS.get(self.colormap_var.get(), cv.COLORMAP_VIRIDIS)
                    color_img_save = cv.applyColorMap(norm_save, cmap_cv_save)
                    # Resize to a reasonable snapshot size, not necessarily current display size
                    # Let's use a fixed medium size or original camera resolution if known
                    # For now, using a fixed size like 640x480 for the saved image
                    snapshot_disp_size = (640, 480) 
                    try: # Attempt to get original frame dimensions for aspect ratio correct resize
                        orig_h, orig_w = self.last_frame.shape[:2]
                        aspect_ratio = orig_w / orig_h
                        target_h = snapshot_disp_size[1]
                        target_w = int(target_h * aspect_ratio)
                        if target_w > snapshot_disp_size[0]: # if too wide, constrain by width
                            target_w = snapshot_disp_size[0]
                            target_h = int(target_w / aspect_ratio)
                        final_save_size = (target_w, target_h)
                    except:
                        final_save_size = snapshot_disp_size # fallback

                    color_img_save = cv.resize(color_img_save, final_save_size, interpolation=cv.INTER_LANCZOS4) # High quality resize
                    # Add overlays to saved image as well (optional, but good for context)
                    # (Code for overlays could be factored into a helper if used identically here)
                    # For brevity, skipping re-drawing overlays on saved image here, but one could add it.
                    
                    img_rgb_save = cv.cvtColor(color_img_save, cv.COLOR_BGR2RGB)
                    img_pil_save = Image.fromarray(img_rgb_save)
                    img_pil_save.save(img_filename, "PNG")
                    self.set_status(f"Snapshot saved: {csv_filename} and {img_filename}")
                else:
                     self.set_status(f"Snapshot data saved to {csv_filename} (image not available)")

            except Exception as e:
                self.set_status(f"Snapshot save failed: {e}")
        else:
            self.set_status("No thermal frame data to save.")

    def stop(self):
        self.running = False
        if self.after_id:
            self.after_cancel(self.after_id) 