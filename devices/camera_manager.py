import serial.tools.list_ports
from senxor.interfaces import MI_VID, MI_PIDs
from .camera import SenxorCamera # Use relative import
import time # Added for __main__ test block
import threading # For hotplug monitor

class CameraManager:
    """Manages multiple SenxorCamera instances."""
    def __init__(self):
        self.cameras = [] # List of SenxorCamera instances
        self.camera_ports = [] # List of discovered COM ports with Senxor cameras
        self._hotplug_running = False
        self._hotplug_thread = None
        self._on_change_callback = None

    def discover_cameras(self):
        """Discovers all available Senxor camera ports."""
        self.camera_ports = []
        print("CameraManager: Discovering Senxor cameras...")
        for p in serial.tools.list_ports.comports():
            if p.vid == MI_VID and p.pid in MI_PIDs:
                self.camera_ports.append(p.device)
        if self.camera_ports:
            print(f"CameraManager: Found cameras on ports: {', '.join(self.camera_ports)}")
        else:
            print("CameraManager: No Senxor cameras found.")
        return self.camera_ports

    def connect_and_start_all(self, stream_fps=15, with_header=True):
        """
        Connects to all discovered cameras and starts their streaming threads.
        Clears existing cameras before connecting.
        """
        self.stop_all_streams() # Stop and clear any existing cameras first
        self.cameras = []
        
        if not self.camera_ports:
            self.discover_cameras()

        if not self.camera_ports:
            print("CameraManager: No camera ports to connect to.")
            return False

        print(f"CameraManager: Connecting and starting {len(self.camera_ports)} camera(s)...")
        all_started_successfully = True
        for port in self.camera_ports:
            print(f"CameraManager: Initializing camera on port {port}...")
            cam = SenxorCamera(port=port, stream_fps=stream_fps, with_header=with_header)
            if cam.is_connected:
                if cam.start_streaming(): # start_streaming now calls _configure if needed
                    self.cameras.append(cam)
                    print(f"CameraManager: Successfully started camera on {port}.")
                else:
                    print(f"CameraManager: Failed to start streaming for camera on {port} though it connected.")
                    all_started_successfully = False
            else:
                print(f"CameraManager: Failed to connect to camera on {port}.")
                all_started_successfully = False
        
        if self.cameras:
            num_successful = len(self.cameras)
            print(f"CameraManager: Successfully connected and started {num_successful}/{len(self.camera_ports)} camera(s).")
        else:
            print(f"CameraManager: No cameras were successfully started.")
            
        return all_started_successfully and len(self.cameras) > 0

    def stop_all_streams(self):
        """Stops streaming and hardware for all managed cameras."""
        print(f"CameraManager: Stopping all {len(self.cameras)} camera streams...")
        for cam in self.cameras:
            try:
                cam.stop() # SenxorCamera.stop() now handles stop_streaming and mi48.stop()
            except Exception as e:
                print(f"CameraManager: Error stopping camera {cam.connected_port or cam._port}: {e}")
        self.cameras = [] # Clear the list of cameras after stopping them
        print("CameraManager: All camera streams stopped and list cleared.")

    def get_all_cameras(self) -> list[SenxorCamera]:
        """Returns a list of all currently connected and streaming SenxorCamera instances."""
        return [cam for cam in self.cameras if cam.is_connected and cam.is_streaming]

    def get_all_latest_frames_and_headers(self) -> list[tuple]:
        """
        Returns a list of (frame, header) tuples from all streaming cameras.
        Each entry can be (None, None) if a camera failed to provide a frame.
        """
        frames_data = []
        for cam in self.get_all_cameras(): # only from active cameras
            frames_data.append(cam.get_latest_frame_and_header())
        return frames_data

    # --- Hotplug Monitoring ---
    def start_hotplug_monitor(self, poll_interval=2.0, on_change=None):
        """Start a background thread to monitor for camera hotplug events."""
        if self._hotplug_running:
            print("CameraManager: Hotplug monitor already running.")
            return
        self._hotplug_running = True
        self._on_change_callback = on_change
        self._hotplug_thread = threading.Thread(target=self._hotplug_loop, args=(poll_interval,), daemon=True)
        self._hotplug_thread.start()
        print("CameraManager: Hotplug monitor started.")

    def stop_hotplug_monitor(self):
        """Stop the hotplug monitor thread."""
        self._hotplug_running = False
        if self._hotplug_thread:
            self._hotplug_thread.join(timeout=2)
            print("CameraManager: Hotplug monitor stopped.")

    def _hotplug_loop(self, poll_interval):
        prev_ports = set(self.camera_ports)
        while self._hotplug_running:
            self.discover_cameras()
            current_ports = set(self.camera_ports)
            if current_ports != prev_ports:
                print(f"CameraManager: Hotplug event detected. Ports changed: {prev_ports} -> {current_ports}")
                self.connect_and_start_all()  # This will add new cameras and start them
                if self._on_change_callback:
                    try:
                        self._on_change_callback()
                    except Exception as e:
                        print(f"CameraManager: Error in hotplug callback: {e}")
                prev_ports = current_ports
            time.sleep(poll_interval)

    def __del__(self):
        print("CameraManager: __del__ called. Stopping all streams and hotplug monitor.")
        self.stop_hotplug_monitor()
        self.stop_all_streams()

# Example Usage (for testing purposes, typically done in main.py)
if __name__ == '__main__':
    manager = CameraManager()
    manager.discover_cameras()
    
    if manager.camera_ports:
        print(f"Found cameras: {manager.camera_ports}")
        if manager.connect_and_start_all(stream_fps=10):
            print("Cameras started. Attempting to get frames for 5 seconds...")
            try:
                for i in range(25): # ~5 seconds if fps is 10 and sleep is 0.2
                    all_frames_headers = manager.get_all_latest_frames_and_headers()
                    print(f"Collected {len(all_frames_headers)} frame sets.")
                    for idx, (frame, header) in enumerate(all_frames_headers):
                        port = manager.cameras[idx].connected_port if idx < len(manager.cameras) else 'Unknown'
                        if frame is not None:
                            print(f"  Cam {port}: Frame shape {frame.shape}, Header frame_counter: {header.get('frame_counter', 'N/A') if header else 'N/A'}")
                        else:
                            print(f"  Cam {port}: No frame")
                    time.sleep(0.2)
            except KeyboardInterrupt:
                print("Test interrupted by user.")
            finally:
                print("Stopping all cameras from test usage...")
                manager.stop_all_streams()
        else:
            print("Failed to start any cameras.")
    else:
        print("No cameras found to test.")
    print("CameraManager test finished.") 