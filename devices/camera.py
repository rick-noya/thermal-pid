import sys
from senxor.utils import connect_senxor, data_to_frame


class SenxorCamera:
    """High-level wrapper around the MI48 thermal camera.

    Encapsulates connection, configuration and frame acquisition logic so that
    the rest of the codebase never has to interact with the low-level MI48 API
    directly.  This keeps the application layer cleaner and makes it easier to
    swap the camera implementation in the future.
    """

    def __init__(self, port: str = "COM9", stream_fps: int = 15, *, with_header: bool = True):
        self._port = port.upper() if port else None
        self._stream_fps = stream_fps
        self._with_header = with_header
        self.mi48 = None  # will be initialised by _connect()
        self.connected_port = None
        self.port_names = []

        self._connect()
        self._configure()

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def read_raw(self):
        """Return the raw (1-D numpy array) sample and header from the camera."""
        return self.mi48.read()

    def read_frame(self):
        """Return a 2-D temperature frame (shape 80×62) and header."""
        data, header = self.read_raw()
        if data is None:
            return None, header
        frame = data_to_frame(data, (80, 62), hflip=False)
        return frame, header

    def stop(self):
        if self.mi48 is not None:
            self.mi48.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self):
        mi48, connected_port, port_names = connect_senxor(src=self._port)
        self.port_names = port_names
        self.connected_port = connected_port

        if mi48 is None:
            raise ConnectionError(
                f"Failed to connect to the Senxor device on {self._port}.\n"
                f"Detected Senxor ports: {', '.join(port_names) if port_names else 'None'}"
            )
        self.mi48 = mi48

    def _configure(self):
        """Apply sensible default configuration for streaming mode."""
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