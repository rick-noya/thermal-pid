import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np
import cv2 as cv
from collections import deque
from .utils import Tooltip
import logging

logger = logging.getLogger(__name__)

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
    def __init__(self, master, camera, trend_graph=None, pid=None, siggen=None, osc=None, set_status=None, style='Content.TFrame', **kwargs):
        super().__init__(master, style=style, **kwargs)
        self.camera = camera
        self.trend_graph = trend_graph
        self.pid = pid
        self.siggen = siggen
        self.osc = osc
        self.set_status = set_status or (lambda msg: None)
        
        self.camera_aspect_ratio = 80.0 / 62.0 # Store camera aspect ratio W/H

        self.img_label = ttk.Label(self) # No specific style, will inherit from parent or default TFrame
        self.img_label.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        self.img_label.configure(anchor=tk.CENTER) # Center the image within the label

        self.last_frame = None
        # self.last_overlay = None # Not used
        self.last_render_size = (int(300 * self.camera_aspect_ratio), 300) # Initial default, will be updated by configure
        self.after_id = None
        self.update_interval = 100  # ms (10 FPS)
        self.running = True
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # --- Controls frame ---
        controls_frame = ttk.Frame(self, style='Content.TFrame', padding=(5,5))
        controls_frame.grid(row=1, column=0, sticky='ew', padx=5, pady=5)
        # Configure columns for even spacing of control groups
        controls_frame.columnconfigure(0, weight=1) # Smoothing Group (Hot)
        controls_frame.columnconfigure(1, weight=1) # Smoothing Group (Cold) - Note: smoothing_group spans 2 cols
        controls_frame.columnconfigure(2, weight=0) # Display Options Group
        controls_frame.columnconfigure(3, weight=0) # Sample Number 
        controls_frame.columnconfigure(4, weight=1) # Colormap 
        controls_frame.columnconfigure(5, weight=0) # Snapshot button

        # Smoothing controls group
        smoothing_group = ttk.Frame(controls_frame, style='Content.TFrame')
        smoothing_group.grid(row=0, column=0, columnspan=2, sticky='ew', padx=(0,5)) # Spans 2 logical columns
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

        # Display Options Group (New)
        display_options_group = ttk.Frame(controls_frame, style='Content.TFrame')
        display_options_group.grid(row=0, column=2, sticky='w', padx=5, pady=2) # Placed after smoothing

        self.show_hot_spot_var = tk.BooleanVar(value=True)
        hot_spot_check = ttk.Checkbutton(display_options_group, text="Hot Spot", variable=self.show_hot_spot_var, command=self.redraw_last_frame_if_exists, style='Content.TCheckbutton')
        hot_spot_check.grid(row=0, column=0, sticky='w', padx=2)
        Tooltip(hot_spot_check, "Toggle visibility of the hot spot marker and temperature.")

        self.show_cold_spot_var = tk.BooleanVar(value=True)
        cold_spot_check = ttk.Checkbutton(display_options_group, text="Cold Spot", variable=self.show_cold_spot_var, command=self.redraw_last_frame_if_exists, style='Content.TCheckbutton')
        cold_spot_check.grid(row=1, column=0, sticky='w', padx=2)
        Tooltip(cold_spot_check, "Toggle visibility of the cold spot marker and temperature.")

        # Sample Number Input Group
        sample_info_group = ttk.Frame(controls_frame, style='Content.TFrame')
        sample_info_group.grid(row=0, column=3, sticky='ew', padx=5) # Shifted to column 3
        sample_info_group.columnconfigure(1, weight=1) # Entry expands
        ttk.Label(sample_info_group, text="Sample #:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=(5,2), pady=2)
        self.sample_number_var = tk.StringVar()
        sample_entry = ttk.Entry(sample_info_group, textvariable=self.sample_number_var, width=10)
        sample_entry.grid(row=0, column=1, sticky='ew', padx=(0,5), pady=2)
        Tooltip(sample_entry, "Enter the sample identifier for this test run.")

        # Colormap selector group
        colormap_group = ttk.Frame(controls_frame, style='Content.TFrame')
        colormap_group.grid(row=0, column=4, sticky='ew', padx=5) # Shifted to column 4
        colormap_group.columnconfigure(1, weight=1)
        ttk.Label(colormap_group, text="Colormap:", style='Content.TLabel').grid(row=0, column=0, sticky='w', padx=2, pady=2)
        self.colormap_var = tk.StringVar(value='Viridis') # Changed default to Viridis
        colormap_menu = ttk.OptionMenu(colormap_group, self.colormap_var, self.colormap_var.get(), *COLORMAPS.keys())
        colormap_menu.grid(row=0, column=1, sticky='ew', padx=2, pady=2)
        Tooltip(colormap_menu, "Select the color palette for the heatmap display.")

        # Snapshot button
        self.snapshot_btn = ttk.Button(controls_frame, text="Save Snapshot", command=self.save_snapshot)
        self.snapshot_btn.grid(row=0, column=5, padx=10, pady=2, sticky='e') # Shifted to column 5
        Tooltip(self.snapshot_btn, "Save the current thermal data as a CSV file and image.")

        # Hot/cold position history (deque for last N)
        self.hot_history = deque(maxlen=self.hot_smooth_len_var.get())
        self.cold_history = deque(maxlen=self.cold_smooth_len_var.get())

        self.img_label.bind('<Configure>', self.on_img_label_resize)
        Tooltip(self.img_label, "Live thermal image. Drag the window divider to resize.")
        self.update_image()

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

    def redraw_last_frame_if_exists(self):
        if self.last_frame is not None:
            self.render_frame(self.last_frame, size=self.last_render_size)

    def on_img_label_resize(self, event):
        allocated_w, allocated_h = event.width, event.height
        if allocated_w < 10 or allocated_h < 10: # Prevent division by zero or too small sizes
            return

        # Calculate render_w and render_h to maintain aspect ratio
        # Camera aspect ratio is W/H = 80/62
        
        # If allocated space is wider than camera aspect ratio (limited by height)
        if (allocated_w / allocated_h) > self.camera_aspect_ratio:
            render_h = allocated_h
            render_w = int(allocated_h * self.camera_aspect_ratio)
        # Else (allocated space is taller or same aspect ratio, limited by width)
        else:
            render_w = allocated_w
            render_h = int(allocated_w / self.camera_aspect_ratio)

        # Ensure minimum size for rendering to avoid errors with cv.resize
        render_w = max(render_w, 1)
        render_h = max(render_h, 1)

        self.last_render_size = (render_w, render_h)
        
        if self.last_frame is not None:
            # Pass the aspect-corrected size to render_frame
            self.render_frame(self.last_frame, size=self.last_render_size)

    def update_image(self):
        if not self.running:
            return
        frame, header = self.camera.read_frame()
        if frame is not None:
            self.last_frame = frame.copy()
            # Use the aspect-corrected size for rendering
            self.render_frame(frame, size=self.last_render_size)
            # Push data to trend graph
            min_temp = np.min(frame)
            max_temp = np.max(frame)
            avg_temp = np.mean(frame)

            # Fetch data from oscilloscope
            # These will be the actual measured values if scope is connected and running
            measured_voltage = 0.0
            measured_current = 0.0
            measured_power = 0.0
            if self.osc and self.osc.is_connected:
                try:
                    v, c, p = self.osc.get_voltage_current_power()
                    measured_voltage = v if v is not None else 0.0
                    measured_current = c if c is not None else 0.0
                    measured_power = p if p is not None else 0.0
                except Exception as e:
                    # self.set_status(f"Oscilloscope read error: {e}") # Can be noisy
                    logger.warning(f"Oscilloscope read error in HeatmapView: {e}")
                    # Keep defaults if error
            
            voltage_to_graph = 0.0 # This is the value that goes to the graph's "voltage" data series

            if self.pid and self.siggen and self.pid.auto_mode:
                current_temp_for_pid = max_temp
                pid_output_voltage = self.pid(current_temp_for_pid)
                
                if self.siggen.is_open:
                    try:
                        self.siggen.set_voltage(pid_output_voltage)
                        # When PID is active, the primary "voltage" for the trend could be the PID output
                        # or the measured voltage. Let's decide: graph the PID setpoint voltage.
                        voltage_to_graph = pid_output_voltage 
                    except Exception as e:
                        self.set_status(f"SigGen Error: {e}")
                        voltage_to_graph = 0.0 # Fallback if SigGen error
                else:
                    voltage_to_graph = 0.0 # PID on, but SigGen not open
            else:
                # PID is off. Graph the measured voltage from the oscilloscope.
                voltage_to_graph = measured_voltage
            
            if self.trend_graph:
                # Pass measured_voltage, measured_current, measured_power for the selectable right axis.
                # voltage_to_graph is specifically for the primary "Voltage (V)" data series if selected on right axis,
                # or if we want a dedicated non-selectable line for PID output (not current design).
                # For now, the TrendGraph's `voltage_data` will receive `voltage_to_graph`.
                self.trend_graph.add_point(max_temp, min_temp, avg_temp, 
                                           voltage_to_graph,  # This feeds TrendGraph's self.voltage_data
                                           measured_current,  # This feeds TrendGraph's self.current_data
                                           measured_power)    # This feeds TrendGraph's self.power_data

        self.after_id = self.after(self.update_interval, self.update_image)

    def render_frame(self, frame, size=(400, 310)):
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
                
                if self.show_hot_spot_var.get(): # Check visibility
                    if len(self.hot_history) > 0:
                        hot_avg = np.mean(self.hot_history, axis=0)
                        hot_pos = (int(hot_avg[0]), int(hot_avg[1]))
                        # Draw outlined text for hot spot
                        text_hot = f"{np.max(frame):.1f}C" # Corrected: was .1f0C
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

                if self.show_cold_spot_var.get(): # Check visibility
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