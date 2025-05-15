import tkinter as tk
from tkinter import messagebox
import os
import sys
import logging
import datetime
from devices.camera_manager import CameraManager
from devices.data_aggregator import DataAggregator
from devices.signal_generator import SignalGenerator
from controllers.pid_controller import TemperaturePID
from ui.app import SenxorApp
from ui.crash_reporter import crash_reporter, install_global_handler
import config
import time

# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = os.path.join(LOG_DIR, f"thermal_pid_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)

# Root logger configuration
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger("thermal-pid")

# Initialize and set up the crash reporter
APP_VERSION = "1.0.0"  # Update this with your actual version
crash_reporter.app_version = APP_VERSION
install_global_handler()

def main():
    try:
        logger.info(f"Application starting (version {APP_VERSION})")
        # Capture basic system info for potential crash reports
        crash_reporter.capture_app_state(
            python_version=sys.version,
            pid_defaults=str(config.PID_DEFAULTS),
            max_voltage=config.MAX_VOLTAGE_DEFAULT
        )
        
        camera_manager = CameraManager()
        cameras_started = camera_manager.connect_and_start_all(stream_fps=config.STREAM_FPS)

        if not cameras_started or not camera_manager.get_all_cameras():
            logger.warning("No cameras were detected or started successfully")
            messagebox.showwarning("Camera System Issue", 
                                "No Senxor/MI48 cameras were detected, connected, or started successfully.\n"
                                "Application will run with limited camera functionality.")
        else:
            num_cams = len(camera_manager.get_all_cameras())
            logger.info(f"{num_cams} camera(s) successfully initialized and streaming")
            messagebox.showinfo("Cameras Initialized", 
                                f"{num_cams} camera(s) successfully initialized and streaming.")

        # Update crash reporter with camera information
        cam_info = []
        for cam in camera_manager.get_all_cameras():
            cam_info.append({
                "port": cam.connected_port,
                "status": "connected" if cam.connected else "disconnected"
            })
        crash_reporter.capture_app_state(cameras=cam_info)

        with crash_reporter.error_context({"component": "DataAggregator"}):
            data_aggregator = DataAggregator(camera_manager)

        with crash_reporter.error_context({"component": "PID Controller"}):
            pid = TemperaturePID(
                **config.PID_DEFAULTS,
                data_aggregator=data_aggregator,
                pid_camera_indices=None,
                pid_aggregation_mode='overall_max'
            )

            # Pause PID by default so no control output is generated until the user
            # explicitly starts the loop from the UI (Start PID button).
            pid.pause()

        with crash_reporter.error_context({"component": "Signal Generator"}):
            siggen = SignalGenerator(
                port=config.DEFAULT_PORT_SIGGEN, 
                baud=config.SIGGEN_BAUD, 
                timeout=config.SIGGEN_TIMEOUT
            )
            # Update crash reporter with signal generator info
            crash_reporter.capture_app_state(
                signal_generator={
                    "port": config.DEFAULT_PORT_SIGGEN,
                    "connected": siggen.is_open if hasattr(siggen, "is_open") else False
                }
            )

        with crash_reporter.error_context({"component": "Main UI"}):
            root = tk.Tk()
            app = SenxorApp(root, camera_manager=camera_manager, siggen=siggen, pid=pid)
        
        try:
            logger.info("Entering main event loop")
            root.mainloop()
        finally:
            logger.info("Main event loop exited")
            print("Main: Application exiting. Stopping all camera streams...")
            if camera_manager:
                camera_manager.stop_all_streams()
            print("Main: Camera streams stopped. Exiting.")
            logger.info("Application shutdown complete")
    
    except Exception as e:
        logger.exception("Fatal error during application startup")
        # The global exception handler will take care of showing the error
        # and generating the crash report
        raise

if __name__ == "__main__":
    main() 