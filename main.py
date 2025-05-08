import tkinter as tk
from tkinter import messagebox
from devices.camera import SenxorCamera
from devices.signal_generator import SignalGenerator
from controllers.pid_controller import TemperaturePID
from ui.app import SenxorApp
import config

def main():
    camera = SenxorCamera(port=None, stream_fps=config.STREAM_FPS)
    if not camera.is_connected:
        messagebox.showwarning("Camera Not Detected", 
                               "No Senxor/MI48 camera was detected or connected.\n"
                               "Application will run with limited functionality.")

    siggen = SignalGenerator(port=config.DEFAULT_PORT_SIGGEN, baud=config.SIGGEN_BAUD, timeout=config.SIGGEN_TIMEOUT)
    pid    = TemperaturePID(**config.PID_DEFAULTS)

    root = tk.Tk()
    app = SenxorApp(root, camera=camera, siggen=siggen, pid=pid)
    root.mainloop()

if __name__ == "__main__":
    main() 