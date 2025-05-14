import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import numpy as np

class ROIStitchDialog(tk.Toplevel):
    def __init__(self, master, camera_views, roi_store=None, on_save=None, **kwargs):
        super().__init__(master, **kwargs)
        self.title("ROI Selection & Image Stitching")
        self.transient(master)
        self.grab_set()  # Non-blocking true modal
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.geometry("700x600")

        self.camera_views = camera_views  # List of HeatmapView instances
        self.current_cam_idx = 0
        self.roi_store = roi_store if roi_store is not None else {}
        self.on_save = on_save
        self.undo_stack = []  # For undoing point selections

        self._build_ui()
        self._load_current_image()
        self._draw_overlay()
        self._update_status()

    def _build_ui(self):
        # Instruction label for ROI order
        self.instruction_label = ttk.Label(self, text="Select ROI corners in this order: top-left, top-right, bottom-right, bottom-left", foreground='blue')
        self.instruction_label.pack(pady=(8, 0))
        # Camera selector (if multiple cameras)
        if len(self.camera_views) > 1:
            cam_names = [getattr(cam.camera, 'connected_port', f"Camera {i+1}") for i, cam in enumerate(self.camera_views)]
            self.cam_var = tk.StringVar(value=cam_names[self.current_cam_idx])
            cam_menu = ttk.OptionMenu(self, self.cam_var, cam_names[self.current_cam_idx], *cam_names, command=self._on_camera_change)
            cam_menu.pack(pady=8)

        # Include in Stitching checkbox
        self.include_vars = [tk.BooleanVar(value=True) for _ in self.camera_views]
        self.include_chk = ttk.Checkbutton(self, text='Include in Stitching', variable=self.include_vars[self.current_cam_idx], command=self._update_status)
        self.include_chk.pack(pady=(0, 8))

        # Image display
        self.img_canvas = tk.Canvas(self, width=640, height=480, bg='black', cursor='cross')
        self.img_canvas.pack(fill='both', expand=True, padx=10, pady=10)
        self.img_canvas.bind('<Button-1>', self._on_canvas_click)

        # Status label
        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(self, textvariable=self.status_var, anchor='w')
        self.status_label.pack(fill='x', padx=10, pady=(0, 5))

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill='x', padx=10, pady=10)
        self.undo_btn = ttk.Button(btn_frame, text='Undo', command=self._undo_point)
        self.undo_btn.pack(side='left', padx=5)
        self.reset_btn = ttk.Button(btn_frame, text='Reset', command=self._reset_points)
        self.reset_btn.pack(side='left', padx=5)
        self.save_img_btn = ttk.Button(btn_frame, text='Save Image+Array', command=self._save_stitched, state='disabled')
        self.save_img_btn.pack(side='right', padx=5)
        self.cancel_btn = ttk.Button(btn_frame, text='Cancel', command=self.on_cancel)
        self.cancel_btn.pack(side='right', padx=5)

    def _load_current_image(self):
        # Get the latest frame from the current camera view
        cam_view = self.camera_views[self.current_cam_idx]
        frame = getattr(cam_view, 'last_frame', None)
        if frame is not None:
            # Normalize and convert to RGB for display
            import numpy as np
            import cv2 as cv
            min_temp = np.min(frame)
            max_temp = np.max(frame)
            norm = ((frame - min_temp) / (max_temp - min_temp + 1e-6) * 255).astype(np.uint8)
            cmap_name = getattr(cam_view, 'colormap_var', None)
            cmap = 'Viridis'
            if cmap_name is not None:
                cmap = cmap_name.get() if hasattr(cmap_name, 'get') else str(cmap_name)
            COLORMAPS = getattr(cam_view, 'COLORMAPS', None)
            if COLORMAPS is None:
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
            cmap_cv = COLORMAPS.get(cmap, cv.COLORMAP_VIRIDIS)
            color_img = cv.applyColorMap(norm, cmap_cv)
            color_img = cv.resize(color_img, (640, 480), interpolation=cv.INTER_LINEAR)
            img_rgb = cv.cvtColor(color_img, cv.COLOR_BGR2RGB)
            self._img_pil = Image.fromarray(img_rgb)
            self._img_tk = ImageTk.PhotoImage(self._img_pil)
            self.img_canvas.create_image(0, 0, anchor='nw', image=self._img_tk)
        else:
            self.img_canvas.delete('all')
            self._img_pil = None
            self._img_tk = None
        # Load existing ROI points for this camera if present
        cam_id = self._get_current_camera_id()
        self.roi_points = list(self.roi_store.get(cam_id, []))
        self.undo_stack = []

    def _draw_overlay(self):
        self.img_canvas.delete('roi_overlay')
        # Draw points and lines
        if hasattr(self, '_img_tk') and self._img_tk:
            self.img_canvas.create_image(0, 0, anchor='nw', image=self._img_tk, tags='roi_overlay')
        r = 6
        for i, pt in enumerate(self.roi_points):
            x, y = pt
            self.img_canvas.create_oval(x-r, y-r, x+r, y+r, outline='yellow', width=2, tags='roi_overlay')
            self.img_canvas.create_text(x, y-12, text=str(i+1), fill='yellow', font=('Segoe UI', 10, 'bold'), tags='roi_overlay')
        if len(self.roi_points) > 1:
            self.img_canvas.create_line(*sum(self.roi_points, ()), fill='yellow', width=2, tags='roi_overlay')
        if len(self.roi_points) == 4:
            self.img_canvas.create_line(*self.roi_points[3], *self.roi_points[0], fill='yellow', width=2, tags='roi_overlay')

    def _on_canvas_click(self, event):
        if len(self.roi_points) >= 4:
            return
        x, y = event.x, event.y
        self.undo_stack.append(list(self.roi_points))
        self.roi_points.append((x, y))
        # Save ROI points immediately after each click
        cam_id = self._get_current_camera_id()
        self.roi_store[cam_id] = list(self.roi_points)
        if self.on_save:
            self.on_save(self.roi_store)
        self._draw_overlay()
        self._update_status()

    def _undo_point(self):
        if self.undo_stack:
            self.roi_points = self.undo_stack.pop()
            self._draw_overlay()
            self._update_status()

    def _reset_points(self):
        if self.roi_points:
            self.undo_stack.append(list(self.roi_points))
        self.roi_points = []
        self._draw_overlay()
        self._update_status()

    def _save_roi(self):
        # No longer needed, removed from UI
        pass

    def on_cancel(self):
        self.destroy()

    def _on_camera_change(self, value):
        idx = 0
        for i, cam in enumerate(self.camera_views):
            name = getattr(cam.camera, 'connected_port', f"Camera {i+1}")
            if name == value:
                idx = i
                break
        self.current_cam_idx = idx
        self.include_chk.config(variable=self.include_vars[self.current_cam_idx])
        self._load_current_image()
        self._draw_overlay()
        self._update_status()

    def _get_current_camera_id(self):
        cam = self.camera_views[self.current_cam_idx]
        return getattr(cam.camera, 'connected_port', f"Camera{self.current_cam_idx+1}")

    def _update_status(self):
        included = [i for i, var in enumerate(self.include_vars) if var.get()]
        all_ready = all(len(self.roi_store.get(self._get_camera_id(self.camera_views[i]), [])) == 4 for i in included)
        if len(self.roi_points) < 4:
            self.status_var.set(f"Click to select ROI corners ({len(self.roi_points)}/4 selected). Undo/Reset available.")
            self.save_img_btn.config(state='disabled')
        elif not included:
            self.status_var.set("No cameras selected for stitching. Check 'Include in Stitching' for at least one camera.")
            self.save_img_btn.config(state='disabled')
        elif not all_ready:
            self.status_var.set("ROI ready for this camera. Complete all included cameras to enable Save Image+Array.")
            self.save_img_btn.config(state='disabled')
        else:
            self.status_var.set("ROI ready. Click Save Image+Array to export stitched data.")
            self.save_img_btn.config(state='normal')

    def _get_camera_id(self, cam):
        return getattr(cam.camera, 'connected_port', f"Camera{self.camera_views.index(cam)+1}")

    def _save_stitched(self):
        import numpy as np
        from tkinter.filedialog import asksaveasfilename
        from PIL import Image
        import cv2 as cv
        import traceback
        try:
            included = [i for i, var in enumerate(self.include_vars) if var.get()]
            if not included:
                self.status_var.set("No cameras selected for stitching.")
                return
            stitched_arrays = []
            stitched_images = []
            dtype = None
            for i in included:
                cam = self.camera_views[i]
                frame = getattr(cam, 'last_frame', None)
                roi = self.roi_store.get(self._get_camera_id(cam), None)
                if frame is None or roi is None or len(roi) != 4:
                    self.status_var.set("All included cameras must have 4 ROI points and valid frames.")
                    return
                # Ensure frame is float32 for map_coordinates
                frame = np.asarray(frame, dtype=np.float32)
                # Bilinear mapping from 4 ROI points to 80x62 output
                h_out, w_out = 62, 80
                roi = np.array(roi, dtype=np.float32)
                dst = np.array([[0,0],[w_out-1,0],[w_out-1,h_out-1],[0,h_out-1]], dtype=np.float32)
                grid_x = np.zeros((h_out, w_out), dtype=np.float32)
                grid_y = np.zeros((h_out, w_out), dtype=np.float32)
                for v in range(h_out):
                    for u in range(w_out):
                        s = u / (w_out-1)
                        t = v / (h_out-1)
                        px = (1-s)*(1-t)*roi[0,0] + s*(1-t)*roi[1,0] + s*t*roi[2,0] + (1-s)*t*roi[3,0]
                        py = (1-s)*(1-t)*roi[0,1] + s*(1-t)*roi[1,1] + s*t*roi[2,1] + (1-s)*t*roi[3,1]
                        grid_x[v,u] = px
                        grid_y[v,u] = py
                from scipy.ndimage import map_coordinates
                unwrapped = map_coordinates(frame, [grid_y.ravel(), grid_x.ravel()], order=1, mode='reflect').reshape((h_out, w_out))
                if dtype is None:
                    dtype = frame.dtype if hasattr(frame, 'dtype') else np.uint16
                stitched_arrays.append(unwrapped)
                min_temp = np.min(unwrapped)
                max_temp = np.max(unwrapped)
                norm = ((unwrapped - min_temp) / (max_temp - min_temp + 1e-6) * 255).astype(np.uint8)
                cmap_name = getattr(cam, 'colormap_var', None)
                cmap = 'Viridis'
                if cmap_name is not None:
                    cmap = cmap_name.get() if hasattr(cmap_name, 'get') else str(cmap_name)
                COLORMAPS = getattr(cam, 'COLORMAPS', None)
                if COLORMAPS is None:
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
                cmap_cv = COLORMAPS.get(cmap, cv.COLORMAP_VIRIDIS)
                color_img = cv.applyColorMap(norm, cmap_cv)
                img_rgb = cv.cvtColor(color_img, cv.COLOR_BGR2RGB)
                stitched_images.append(Image.fromarray(img_rgb))
            # Flatten the cylinder by stitching side-by-side (left→right)
            stitched_array = np.hstack(stitched_arrays)
            if dtype is None:
                dtype = np.uint16
            stitched_array_int = np.round(stitched_array).astype(dtype)
            print(f"[DEBUG] stitched_array dtype: {stitched_array.dtype}, shape: {stitched_array.shape}")
            print(f"[DEBUG] stitched_array_int dtype: {stitched_array_int.dtype}, shape: {stitched_array_int.shape}")
            # Compose RGB preview side-by-side as well
            stitched_img = Image.new('RGB', (sum(im.width for im in stitched_images), stitched_images[0].height))
            x_offset = 0
            for im in stitched_images:
                stitched_img.paste(im, (x_offset, 0))
                x_offset += im.width
            fname = asksaveasfilename(defaultextension='.csv', filetypes=[('CSV Matrix','*.csv')], title='Save Stitched Array')
            if not fname:
                return
            print(f"[DEBUG] Saving CSV to: {fname}")
            try:
                np.savetxt(fname, stitched_array_int, delimiter=',', fmt='%d')
            except Exception as e:
                print(f"[ERROR] np.savetxt failed: {e}")
                traceback.print_exc()
                self.status_var.set(f"Error: {e}")
                return
            img_fname = fname.rsplit('.',1)[0]+'.png'
            print(f"[DEBUG] Saving PNG to: {img_fname}")
            stitched_img.save(img_fname)
            self.status_var.set(f"Saved: {fname} and {img_fname}")
        except Exception as e:
            print(f"[ERROR] Exception in _save_stitched: {e}")
            traceback.print_exc()
            self.status_var.set(f"Error: {e}") 