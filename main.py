import tkinter as tk
from devices.camera import SenxorCamera
from devices.signal_generator import SignalGenerator
from controllers.pid_controller import TemperaturePID
from ui.app import SenxorApp
import config

def main():
    camera = SenxorCamera(port=None, stream_fps=config.STREAM_FPS)
    siggen = SignalGenerator(port=config.DEFAULT_PORT_SIGGEN, baud=config.SIGGEN_BAUD, timeout=config.SIGGEN_TIMEOUT)
    pid    = TemperaturePID(**config.PID_DEFAULTS)

    root = tk.Tk()
    app = SenxorApp(root, camera=camera, siggen=siggen, pid=pid)
    root.mainloop()

if __name__ == "__main__":
    main() 