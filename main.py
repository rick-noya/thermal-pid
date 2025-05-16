import tkinter as tk
from tkinter import messagebox
from devices.camera_manager import CameraManager
from devices.data_aggregator import DataAggregator
from devices.signal_generator import SignalGenerator
from controllers.pid_controller import TemperaturePID
from ui.app import SenxorApp
import config
import time
from updater.update_client import client as auto_update

def main():
    camera_manager = CameraManager()
    cameras_started = camera_manager.connect_and_start_all(stream_fps=config.STREAM_FPS)

    if not cameras_started or not camera_manager.get_all_cameras():
        messagebox.showwarning("Camera System Issue", 
                               "No Senxor/MI48 cameras were detected, connected, or started successfully.\n"
                               "Application will run with limited camera functionality.")
    else:
        num_cams = len(camera_manager.get_all_cameras())
        messagebox.showinfo("Cameras Initialized", 
                            f"{num_cams} camera(s) successfully initialized and streaming.")

    data_aggregator = DataAggregator(camera_manager)

    pid = TemperaturePID(
        **config.PID_DEFAULTS,
        data_aggregator=data_aggregator,
        pid_camera_indices=None,
        pid_aggregation_mode='overall_max'
    )

    # Pause PID by default so no control output is generated until the user
    # explicitly starts the loop from the UI (Start PID button).
    pid.pause()

    siggen = SignalGenerator(
        port=config.DEFAULT_PORT_SIGGEN, 
        baud=config.SIGGEN_BAUD, 
        timeout=config.SIGGEN_TIMEOUT
    )

    root = tk.Tk()
    app = SenxorApp(root, camera_manager=camera_manager, siggen=siggen, pid=pid)
    
    # Kick off a non-blocking update check (will prompt user if a newer version exists)
    auto_update.check_for_updates_async(parent=root)

    try:
        root.mainloop()
    finally:
        print("Main: Application exiting. Stopping all camera streams...")
        if camera_manager:
            camera_manager.stop_all_streams()
        print("Main: Camera streams stopped. Exiting.")

if __name__ == "__main__":
    main() 