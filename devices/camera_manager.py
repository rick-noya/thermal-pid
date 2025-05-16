import serial.tools.list_ports
from senxor.interfaces import MI_VID, MI_PIDs
from .camera import SenxorCamera # Use relative import
import time # Added for __main__ test block
import threading # For hotplug monitor
import config # Import the config module to access CAMERA_PORT_MAPPINGS

class CameraManager:
    """Manages multiple SenxorCamera instances."""
    def __init__(self):
        self.cameras = [] # List of SenxorCamera instances
        # self.camera_ports = [] # No longer just a list of detected ports, managed by mapping
        self._hotplug_running = False
        self._hotplug_thread = None
        self._on_change_callback = None

    def get_connected_camera_serials_and_ports(self):
        """Scans all COM ports, connects to Senxor cameras, and returns a dict of {serial: port}."""
        detected_cameras_info = {}
        ports = serial.tools.list_ports.comports()
        print("CameraManager: Scanning for connected camera serials and ports...")
        for port_info in ports:
            if not (port_info.vid == MI_VID and port_info.pid in MI_PIDs):
                continue # Skip non-Senxor/MI48 ports
            
            port_name = port_info.device
            cam_temp = None
            try:
                print(f"CameraManager: Checking port {port_name}...")
                cam_temp = SenxorCamera(port=port_name, stream_fps=1) # Use low FPS for quick check
                if cam_temp.is_connected and cam_temp.mi48:
                    serial_num = getattr(cam_temp.mi48, 'camera_id_hexsn', None) or getattr(cam_temp.mi48, 'sn', None)
                    if serial_num:
                        detected_cameras_info[serial_num] = port_name
                        print(f"CameraManager: Found camera {serial_num} on {port_name}")
                    else:
                        print(f"CameraManager: Camera on {port_name} connected but no serial number found.")
            except Exception as e:
                print(f"CameraManager: Error probing camera on {port_name}: {e}")
            finally:
                if cam_temp:
                    cam_temp.stop() # Ensure port is released
        return detected_cameras_info

    def connect_and_start_all(self, stream_fps=15, with_header=True):
        """ Connects to cameras based on config.CAMERA_PORT_MAPPINGS. """
        self.stop_all_streams() # Stop and clear any existing cameras first
        self.cameras = []

        configured_mappings = config.CAMERA_PORT_MAPPINGS
        if not configured_mappings:
            print("CameraManager: No camera port mappings found in config.yaml. Please run query_camera_ids.py and update config.")
            # Fallback: Discover and connect to any available cameras if no mapping exists?
            # For now, strictly adhere to mapping if it's intended to be enforced.
            print("CameraManager: Attempting to auto-discover and connect to any available cameras as a fallback.")
            self._connect_auto_discovered(stream_fps,with_header)
            return len(self.cameras) > 0

        print(f"CameraManager: Attempting to connect cameras based on config mapping: {configured_mappings}")
        
        # Get currently connected physical cameras and their actual ports
        # This is a dict of {serial_num: actual_port}
        currently_connected_serials_ports = self.get_connected_camera_serials_and_ports()

        all_started_successfully = True
        cameras_to_start_on_ports = {}

        for serial_num, configured_port in configured_mappings.items():
            if serial_num in currently_connected_serials_ports:
                actual_port = currently_connected_serials_ports[serial_num]
                if actual_port.upper() == configured_port.upper():
                    print(f"CameraManager: Camera {serial_num} found on configured port {configured_port}.")
                    cameras_to_start_on_ports[serial_num] = configured_port
                else:
                    print(f"CameraManager: WARNING - Camera {serial_num} is configured for {configured_port} but found on {actual_port}. Using actual port {actual_port}.")
                    # Decide: use actual_port or configured_port? Forcing configured_port might fail if camera moved.
                    # Using actual_port is safer if the goal is to use the camera regardless of minor port changes.
                    # If strict enforcement is needed, this logic needs to be tighter or only use configured_port.
                    cameras_to_start_on_ports[serial_num] = actual_port # Use the port it's actually on
            else:
                print(f"CameraManager: WARNING - Camera {serial_num} configured for port {configured_port} is not detected.")
                all_started_successfully = False
        
        if not cameras_to_start_on_ports:
            print("CameraManager: No configured cameras found connected. Nothing to start.")
            return False
            
        print(f"CameraManager: Initializing {len(cameras_to_start_on_ports)} mapped camera(s)...")
        for serial_num, port_to_use in cameras_to_start_on_ports.items():
            print(f"CameraManager: Initializing camera {serial_num} on port {port_to_use}...")
            cam = SenxorCamera(port=port_to_use, stream_fps=stream_fps, with_header=with_header)
            # We need to make sure the SenxorCamera instance internally stores its serial number if not already
            # For now, assume it can be retrieved via cam.mi48 properties after connection.
            if cam.is_connected:
                # Store the serial number from config with the camera instance for later reference/sorting
                # This assumes cam.mi48.camera_id_hexsn or cam.mi48.sn will match the serial_num from config
                cam.config_serial_number = serial_num # Add this attribute for robust sorting later
                if cam.start_streaming():
                    self.cameras.append(cam)
                    print(f"CameraManager: Successfully started camera {serial_num} on {port_to_use}.")
                else:
                    print(f"CameraManager: Failed to start streaming for camera {serial_num} on {port_to_use}.")
                    all_started_successfully = False
            else:
                print(f"CameraManager: Failed to connect to camera {serial_num} on {port_to_use}.")
                all_started_successfully = False

        if self.cameras:
            num_successful = len(self.cameras)
            print(f"CameraManager: Successfully connected and started {num_successful}/{len(configured_mappings)} configured camera(s).")
        else:
            print("CameraManager: No configured cameras were successfully started.")
            
        return all_started_successfully and len(self.cameras) > 0

    def _connect_auto_discovered(self, stream_fps=15, with_header=True):
        """Fallback method to discover and connect any cameras if no mapping exists or fails."""
        print("CameraManager: Auto-discovering cameras...")
        discovered_ports = []
        for p in serial.tools.list_ports.comports():
            if p.vid == MI_VID and p.pid in MI_PIDs:
                discovered_ports.append(p.device)
        
        if not discovered_ports:
            print("CameraManager: Auto-discovery: No Senxor cameras found.")
            return False
        
        print(f"CameraManager: Auto-discovery: Found {len(discovered_ports)} potential cameras. Connecting...")
        for port in discovered_ports:
            cam = SenxorCamera(port=port, stream_fps=stream_fps, with_header=with_header)
            if cam.is_connected:
                if cam.start_streaming():
                    self.cameras.append(cam)
                else:
                    print(f"CameraManager: Auto-discovery: Failed to start streaming for {port}.")
            else:
                print(f"CameraManager: Auto-discovery: Failed to connect to {port}.")
        return len(self.cameras) > 0

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
        # Sorting by serial number should happen in the UI layer (SenxorApp) if needed for display order.
        # This manager just provides the list of active cameras.
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
        # Get initial set of connected serials based on config for comparison
        # This needs to be robust. For now, let's assume connect_and_start_all handles changes.
        # A more refined hotplug would compare serial numbers from config vs detected.
        # For now, simple port count change or re-running connect_and_start_all can be a starting point.
        
        # Get an initial list of serial numbers from currently managed cameras for comparison
        # This assumes that self.cameras is populated according to the config initially.
        def get_managed_serials():
            return {getattr(cam, 'config_serial_number', None) for cam in self.cameras if hasattr(cam, 'config_serial_number')}

        prev_managed_serials = get_managed_serials()
        prev_connected_physical_serials = set(self.get_connected_camera_serials_and_ports().keys())

        while self._hotplug_running:
            time.sleep(poll_interval)
            current_connected_physical_serials = set(self.get_connected_camera_serials_and_ports().keys())
            
            # Check if the set of physically connected serials has changed
            # OR if the set of serials we *expect* to manage (from config) is different from what's running.
            expected_serials_from_config = set(config.CAMERA_PORT_MAPPINGS.keys())

            if current_connected_physical_serials != prev_connected_physical_serials or \
               get_managed_serials() != expected_serials_from_config:
                
                print(f"CameraManager: Hotplug event detected.")
                print(f"  Previous physical serials: {prev_connected_physical_serials}")
                print(f"  Current physical serials:  {current_connected_physical_serials}")
                print(f"  Previously managed serials (from config): {prev_managed_serials}")
                print(f"  Expected serials from config: {expected_serials_from_config}")
                
                print("CameraManager: Re-evaluating camera connections based on config...")
                self.connect_and_start_all()  # Re-run connection logic based on config
                
                current_managed_serials = get_managed_serials()
                if self._on_change_callback and (current_managed_serials != prev_managed_serials or current_connected_physical_serials != prev_connected_physical_serials) :
                    print("CameraManager: Invoking on_change_callback due to changes.")
                    try:
                        self._on_change_callback()
                    except Exception as e:
                        print(f"CameraManager: Error in hotplug callback: {e}")
                
                prev_managed_serials = current_managed_serials
                prev_connected_physical_serials = current_connected_physical_serials

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