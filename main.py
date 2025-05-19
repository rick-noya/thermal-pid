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
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import serial

# Setup logging (before application logic)
logs_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file_path = os.path.join(logs_dir, "application.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        RotatingFileHandler(log_file_path, maxBytes=1_000_000, backupCount=3),
        logging.StreamHandler()
    ],
)
logger = logging.getLogger(__name__)
logger.info("Logging initialized. Log file: %s", log_file_path)

# --- SerialStatusBroadcaster: Sends status to ESP32 display over serial ---
class SerialStatusBroadcaster:
    def __init__(self, port, baudrate=115200, max_temp_warning=100.0):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.last_sent = None
        self.lock = threading.Lock()
        self.max_temp_warning = max_temp_warning
        self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info(f"SerialStatusBroadcaster: Connected to {self.port} at {self.baudrate} baud.")
        except Exception as e:
            logger.error(f"SerialStatusBroadcaster: Could not open serial port {self.port}: {e}")
            self.ser = None

    def send_status(self, phase, elapsed, cooling, max_temp=None, cooling_down=False):
        msg = {
            "phase": phase,
            "elapsed": elapsed,
            "cooling": bool(cooling),
            "cooling_down": bool(cooling_down),
        }
        warning = False
        if max_temp is not None:
            msg["max_temp"] = max_temp
            if max_temp >= self.max_temp_warning:
                warning = True
        if warning:
            msg["warning"] = True
        import json
        msg_str = json.dumps(msg) + "\n"
        with self.lock:
            if self.ser and msg_str != self.last_sent:
                try:
                    self.ser.write(msg_str.encode())
                    self.last_sent = msg_str
                except Exception as e:
                    logger.error(f"SerialStatusBroadcaster: Write failed: {e}")
                    self.ser = None
                    self._connect()

    def close(self):
        with self.lock:
            if self.ser:
                try:
                    self.ser.close()
                except Exception:
                    pass
                self.ser = None

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

    # --- SerialStatusBroadcaster setup ---
    SERIAL_PORT = config.ESP32_DISPLAY_SERIAL_PORT
    BAUD_RATE = config.ESP32_DISPLAY_BAUD_RATE
    MAX_TEMP_WARNING = config.ESP32_DISPLAY_MAX_TEMP_WARNING_THRESHOLD
    status_broadcaster = SerialStatusBroadcaster(SERIAL_PORT, baudrate=BAUD_RATE, max_temp_warning=MAX_TEMP_WARNING)

    root = tk.Tk()
    app = SenxorApp(root, camera_manager=camera_manager, siggen=siggen, pid=pid, status_broadcaster=status_broadcaster)
    
    # Kick off a non-blocking update check (will prompt user if a newer version exists)
    auto_update.check_for_updates_async(parent=root)

    # --- Periodically send status to ESP32 ---
    def poll_and_send_status():
        try:
            cp = app.control_panel
            phase = getattr(cp, '_current_phase_desc', 'Idle')
            elapsed = cp.phase_var.get().split(': ', 1)[-1] if ': ' in cp.phase_var.get() else '00:00:00'
            cooling = (phase.lower() == 'cooling')
            cooling_down = cooling  # New field for display
            max_temp = None
            if hasattr(cp, 'data_aggregator') and cp.data_aggregator:
                try:
                    max_temp = cp.data_aggregator.get_frames_for_pid(aggregation_mode='overall_max')
                    if isinstance(max_temp, (list, tuple)):
                        max_temp = max(max_temp)
                except Exception as e:
                    logger.debug(f"Could not get max_temp for status: {e}")
                    max_temp = None
            status_broadcaster.send_status(phase, elapsed, cooling, max_temp, cooling_down=cooling_down)
        except Exception as e:
            logger.error(f"Status broadcast error: {e}")
        root.after(1000, poll_and_send_status)
    root.after(1000, poll_and_send_status)

    try:
        root.mainloop()
    finally:
        print("Main: Application exiting. Stopping all camera streams...")
        if camera_manager:
            camera_manager.stop_all_streams()
        status_broadcaster.close()
        print("Main: Camera streams stopped. Exiting.")

if __name__ == "__main__":
    main() 