import sys
from senxor.utils import connect_senxor, data_to_frame
import serial.tools.list_ports
from senxor.interfaces import MI_VID, MI_PIDs


class SenxorCamera:
    """High-level wrapper around the MI48 thermal camera.

    Encapsulates connection, configuration and frame acquisition logic so that
    the rest of the codebase never has to interact with the low-level MI48 API
    directly.  This keeps the application layer cleaner and makes it easier to
    swap the camera implementation in the future.
    """

    def __init__(self, port: str = None, stream_fps: int = 15, *, with_header: bool = True):
        self.is_connected = False # Initialize connection status
        self._port = None
        # Auto-detect port if not specified or set to 'auto'
        if not port or port.lower() == 'auto':
            try:
                self._port = self._autodetect_port()
            except RuntimeError:
                # self._port remains None, will be handled in _connect
                print("Camera auto-detection failed. Proceeding without camera.") # Or use logging
                pass # Keep self._port as None
        else:
            self._port = port.upper()

        self._stream_fps = stream_fps
        self._with_header = with_header
        self.mi48 = None  # will be initialised by _connect()
        self.connected_port = None
        self.port_names = []

        self._connect()
        if self.is_connected:
            self._configure()

    def _autodetect_port(self):
        # Try to find a port with a Senxor/MI48 device
        for p in serial.tools.list_ports.comports():
            if p.vid == MI_VID and p.pid in MI_PIDs:
                return p.device
        raise RuntimeError("No Senxor/MI48 camera detected on any COM port.")

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def read_raw(self):
        """Return the raw (1-D numpy array) sample and header from the camera."""
        if not self.is_connected or self.mi48 is None:
            return None, None
        return self.mi48.read()

    def read_frame(self):
        """Return a 2-D temperature frame (shape 80×62) and header."""
        if not self.is_connected: # Added check
            return None, None
        data, header = self.read_raw()
        if data is None:
            return None, header
        frame = data_to_frame(data, (80, 62), hflip=False)
        return frame, header

    def stop(self):
        if self.is_connected and self.mi48 is not None:
            self.mi48.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self):
        if self._port is None: # If auto-detection failed or no port was specified
            print("No camera port specified or detected. Cannot connect.") # Or use logging
            self.is_connected = False
            return

        mi48, connected_port, port_names = connect_senxor(src=self._port)
        self.port_names = port_names
        self.connected_port = connected_port

        if mi48 is None:
            # Instead of raising error, set is_connected to False
            print( # Or use logging
                f"Failed to connect to the Senxor device on {self._port}.\\n"
                f"Detected Senxor ports: {', '.join(port_names) if port_names else 'None'}"
            )
            self.is_connected = False
            return # Exit without raising an error
        self.mi48 = mi48
        self.is_connected = True

    def _configure(self):
        """Apply sensible default configuration for streaming mode."""
        if not self.is_connected or self.mi48 is None: # Added check
            return
        m = self.mi48
        m.set_fps(self._stream_fps)
        # Disable default filters – we do our own filtering post-acquisition.
        m.disable_filter(f1=True, f2=True, f3=True)
        m.set_filter_1(85)
        m.enable_filter(f1=True, f2=False, f3=False, f3_ks_5=False)
        m.set_offset_corr(0.0)
        m.set_sens_factor(100)
        m.get_sens_factor()
        m.start(stream=True, with_header=self._with_header) 