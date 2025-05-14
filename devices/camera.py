import sys
from senxor.utils import connect_senxor, data_to_frame
import serial.tools.list_ports
from senxor.interfaces import MI_VID, MI_PIDs
import threading
import time
import numpy as np


class SenxorCamera:
    """High-level wrapper around the MI48 thermal camera.

    Encapsulates connection, configuration and frame acquisition logic so that
    the rest of the codebase never has to interact with the low-level MI48 API
    directly.  This keeps the application layer cleaner and makes it easier to
    swap the camera implementation in the future.
    """

    def __init__(self, port: str = None, stream_fps: int = 15, *, with_header: bool = True):
        self.is_connected = False
        self._port = None
        if not port or port.lower() == 'auto':
            try:
                self._port = self._autodetect_port()
            except RuntimeError:
                print(f"Camera auto-detection failed for port '{port}'. Proceeding without this camera.")
                # self._port remains None, is_connected remains False
                # No need to do more here, _connect will handle self._port being None
        else:
            self._port = port.upper()

        self._stream_fps = stream_fps
        self._with_header = with_header
        self.mi48 = None
        self.connected_port = None # Will be set in _connect
        self.port_names = [] # Will be set in _connect

        # Threading attributes
        self.latest_frame_data = None # Stores (frame, header)
        self.frame_lock = threading.Lock()
        self.streaming_thread = None
        self.is_streaming = False
        self.stop_event = threading.Event() # For cleaner thread termination

        self._connect() # Tries to connect, sets self.is_connected and self.mi48
        
        # Configuration and starting the underlying hardware stream happens in _configure
        # The _acquisition_loop (software streaming) will be started by an explicit call to start_streaming()

    def _autodetect_port(self):
        # Try to find a port with a Senxor/MI48 device
        for p in serial.tools.list_ports.comports():
            if p.vid == MI_VID and p.pid in MI_PIDs:
                # print(f"Auto-detected Senxor/MI48 camera at {p.device}")
                return p.device
        raise RuntimeError("No Senxor/MI48 camera detected on any COM port.")

    # ---------------------------------------------------------------------
    # Public helpers for controlling the stream
    # ---------------------------------------------------------------------
    def start_streaming(self):
        """Starts the software acquisition loop in a separate thread."""
        if not self.is_connected:
            print(f"Camera on port {self._port or 'N/A'} not connected. Cannot start streaming.")
            return False
        if self.is_streaming:
            print(f"Camera on port {self.connected_port} is already streaming.")
            return True

        # Ensure mi48 is configured and hardware stream is started
        # This might have been done at init if is_connected was true, 
        # but it's good to ensure or do it here.
        # For this refactor, let's assume _configure which calls m.start()
        # should be called *before* starting the acquisition loop.
        # If _configure wasn't called at init (e.g. camera connected later), it needs to be callable.
        if self.mi48 and not hasattr(self.mi48, '_is_hardware_streaming'): # Placeholder for check
             self._configure() # This calls mi48.start()

        self.is_streaming = True
        self.stop_event.clear()
        self.streaming_thread = threading.Thread(target=self._acquisition_loop, daemon=True)
        self.streaming_thread.start()
        print(f"Started streaming for camera on {self.connected_port}.")
        return True

    def stop_streaming(self):
        """Stops the software acquisition loop."""
        if not self.is_streaming:
            # print(f"Camera on port {self.connected_port or self._port} is not streaming.")
            return
        
        print(f"Stopping streaming for camera on {self.connected_port or self._port}...")
        self.is_streaming = False
        self.stop_event.set() # Signal the thread to stop
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=2) # Wait for thread to finish
            if self.streaming_thread.is_alive():
                print(f"Warning: Streaming thread for {self.connected_port} did not terminate gracefully.")
        self.streaming_thread = None
        print(f"Streaming stopped for camera on {self.connected_port or self._port}.")
        # Note: This stops the software loop. The underlying mi48.stop() for hardware is in self.stop()

    def _acquisition_loop(self):
        """Internal method run by the streaming thread to acquire frames."""
        while self.is_streaming and not self.stop_event.is_set():
            if not self.mi48:
                time.sleep(0.1) # Wait if mi48 object is not there
                continue
            try:
                # Directly use the logic from the old read_frame/read_raw
                raw_data, header = self.mi48.read() # Equivalent to old self.read_raw()
                
                current_frame = None
                if raw_data is not None:
                    current_frame = np.rot90(data_to_frame(raw_data, (80, 62), hflip=False))

                with self.frame_lock:
                    self.latest_frame_data = (current_frame, header)
                
                # Respect FPS by calculating delay. Crude for now.
                # A more robust way would use timestamps from the camera header if available
                # or a fixed sleep if mi48.read() is blocking appropriately.
                # If mi48.read() blocks until a new frame is ready based on set_fps,
                # then no sleep or a very small one is needed.
                # Assuming mi48.read() is somewhat blocking or handles its own timing:
                time.sleep(1.0 / (self._stream_fps * 2)) # Sleep a bit to yield CPU

            except Exception as e:
                print(f"Error in acquisition loop for {self.connected_port}: {e}")
                # Potentially stop streaming or attempt re-connection logic here
                time.sleep(0.5) # Wait a bit before retrying

    def get_latest_frame_and_header(self):
        """Returns the most recent (frame, header) tuple. Thread-safe."""
        if not self.is_streaming and not self.is_connected: # if not connected, definitely not streaming
             # print(f"Debug: get_latest_frame called but not connected/streaming on {self._port}")
             return None, None
        
        frame_data_copy = None
        with self.frame_lock:
            if self.latest_frame_data:
                # Return a copy to avoid issues if the caller modifies the frame later
                # and the internal latest_frame_data is also a reference to it.
                # However, frame is usually a numpy array, header a dict.
                # Numpy arrays are copied by slicing or .copy(). Dicts are shallow copied by .copy().
                frame, header = self.latest_frame_data
                frame_copy = frame.copy() if frame is not None else None
                header_copy = header.copy() if header is not None else None
                frame_data_copy = (frame_copy, header_copy)
        return frame_data_copy if frame_data_copy else (None, None)

    # Deprecate or adapt old read_frame and read_raw if they are called directly from outside
    # For now, get_latest_frame_and_header is the new primary way to get data.
    def read_frame(self):
        """Deprecated. Use get_latest_frame_and_header() when streaming."""
        # print("Warning: read_frame() called. Use get_latest_frame_and_header() for threaded acquisition.")
        if self.is_streaming:
            return self.get_latest_frame_and_header()
        else: # Fallback to old behavior if not streaming (e.g. for single-shot capture if that was a use case)
            if not self.is_connected or self.mi48 is None:
                return None, None
            data, header = self.mi48.read() # direct hardware read
            if data is None:
                return None, header
            frame = np.rot90(data_to_frame(data, (80, 62), hflip=False))
            return frame, header

    def read_raw(self):
        """Return the raw (1-D numpy array) sample and header from the camera.
        Note: For threaded streaming, this might not be what you want.
        Consider get_latest_frame_and_header() which gets processed frames."""
        if not self.is_connected or self.mi48 is None:
            return None, None
        # This is a direct hardware read, bypasses the threaded loop's latest frame.
        return self.mi48.read()


    def stop(self):
        """Stops both the software streaming loop and the hardware stream."""
        print(f"Executing SenxorCamera.stop() for {self.connected_port or self._port}")
        self.stop_streaming() # Stop the software acquisition thread first
        if self.is_connected and self.mi48 is not None:
            print(f"Stopping MI48 hardware for {self.connected_port}...")
            self.mi48.stop() # Stop the hardware device
            print(f"MI48 hardware stopped for {self.connected_port}.")
        self.is_connected = False # Consider if device can be reconnected after stop.
                                  # If mi48.stop() closes port, then is_connected should be False.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self):
        if self._port is None:
            print(f"No camera port specified for connection attempt.")
            self.is_connected = False
            return

        print(f"Attempting to connect to Senxor device on {self._port}...")
        try:
            mi48_obj, connected_port_val, port_names_list = connect_senxor(src=self._port)
            self.port_names = port_names_list
            self.connected_port = connected_port_val

            if mi48_obj is None:
                print(
                    f"Failed to connect to the Senxor device on {self._port}.\n"
                    f"Detected Senxor ports: {', '.join(self.port_names) if self.port_names else 'None'}"
                )
                self.is_connected = False
                self.mi48 = None
            else:
                self.mi48 = mi48_obj
                self.is_connected = True
                print(f"Successfully connected to Senxor device on {self.connected_port}.")
        except Exception as e:
            print(f"Exception during connect_senxor for port {self._port}: {e}")
            self.is_connected = False
            self.mi48 = None
            self.connected_port = None
            self.port_names = []


    def _configure(self):
        """Apply sensible default configuration for streaming mode AND starts hardware stream."""
        if not self.is_connected or self.mi48 is None:
            print(f"Cannot configure camera on {self._port or 'N/A'}: not connected or no mi48 object.")
            return
        
        print(f"Configuring MI48 hardware for {self.connected_port}...")
        try:
            m = self.mi48
            m.set_fps(self._stream_fps)
            m.disable_filter(f1=True, f2=True, f3=True)
            m.set_filter_1(85)
            m.enable_filter(f1=True, f2=False, f3=False, f3_ks_5=False)
            m.set_offset_corr(0.0)
            m.set_sens_factor(100)
            m.get_sens_factor() # Typically called to confirm, might not be necessary
            m.start(stream=True, with_header=self._with_header) # This starts the HARDWARE stream
            # Add a flag to mi48 or here if mi48 doesn't have one, to know hardware is streaming.
            # For example: self.mi48._is_hardware_streaming = True 
            print(f"MI48 hardware configured and started for {self.connected_port}.")
        except Exception as e:
            print(f"Exception during _configure for camera {self.connected_port}: {e}")
            # If configuration fails, perhaps set is_connected to False or handle error appropriately
            # For now, just printing error. The camera might be in an indeterminate state.
            self.is_connected = False # Safer to assume connection is lost/unusable if config fails
            print(f"Camera {self.connected_port} marked as not connected due to configuration error.") 