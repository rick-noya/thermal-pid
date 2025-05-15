import numpy as np
# Assuming CameraManager is in a file that allows this import path
# If camera_manager.py and data_aggregator.py are in the same 'devices' directory:
from .camera_manager import CameraManager

class DataAggregator:
    """Aggregates thermal data from multiple cameras via a CameraManager."""

    def __init__(self, camera_manager: CameraManager):
        if not isinstance(camera_manager, CameraManager):
            raise TypeError("camera_manager must be an instance of CameraManager")
        self.camera_manager = camera_manager

    def get_average_of_mean_temperatures(self) -> float | None:
        """
        Calculates the average of the mean temperatures from all currently valid frames.
        Returns a single float value or None if no valid frames are available.
        """
        all_frames_data = self.camera_manager.get_all_latest_frames_and_headers()
        
        mean_temps = []
        for frame, header in all_frames_data:
            if frame is not None and frame.size > 0:
                # Assuming frame contains temperature values
                mean_temps.append(np.mean(frame))
            # else: print("Aggregator: Skipping None or empty frame")

        if not mean_temps:
            # print("Aggregator: No valid mean temperatures to average.")
            return None
        
        average_of_means = np.mean(mean_temps)
        # print(f"Aggregator: Average of mean temperatures: {average_of_means}")
        return float(average_of_means)

    def get_max_temperature_from_all(self) -> float | None:
        """
        Finds the maximum temperature value across all valid frames from all cameras.
        Returns a single float value or None.
        """
        all_frames_data = self.camera_manager.get_all_latest_frames_and_headers()
        max_temps = []

        for frame, header in all_frames_data:
            if frame is not None and frame.size > 0:
                max_temps.append(np.max(frame))

        if not max_temps:
            return None
        
        return float(np.max(max_temps))

    def get_frames_for_pid(self, camera_indices: list[int] = None, aggregation_mode='average_mean') -> float | None | list:
        """
        Provides data suitable for a PID controller based on specified cameras and mode.
        
        Args:
            camera_indices: Optional list of indices for specific cameras in CameraManager.cameras list.
                            If None, uses all available cameras.
            aggregation_mode: 'average_mean', 'overall_max', or 'individual_means', 'individual_maxs'.
                              'first_valid_mean' gets mean from first camera with valid frame.
                              'raw_frames' returns a list of (frame, header) from selected cameras.

        Returns: 
            A float for aggregated values, a list of floats for individual values, 
            a list of (frame,header) for 'raw_frames', or None if no suitable data.
        """
        active_cameras = self.camera_manager.get_all_cameras() # Gets only active, streaming cameras
        selected_frames_data = []

        if camera_indices is not None:
            for i in camera_indices:
                if 0 <= i < len(active_cameras):
                    selected_frames_data.append(active_cameras[i].get_latest_frame_and_header())
                # else: print(f"Aggregator: Invalid camera index {i} provided.")
        else:
            selected_frames_data = [cam.get_latest_frame_and_header() for cam in active_cameras]

        if not selected_frames_data:
            # print("Aggregator: No cameras selected or available for PID.")
            return None

        valid_frames = [(f, h) for f, h in selected_frames_data if f is not None and f.size > 0]
        if not valid_frames:
            # print("Aggregator: No valid frames from selected cameras for PID.")
            return None

        # --- Aggregation Modes --- 
        if aggregation_mode == 'average_mean':
            means = [np.mean(f) for f, h in valid_frames]
            return float(np.mean(means)) if means else None
        
        elif aggregation_mode == 'overall_max':
            max_values = [np.max(f) for f, h in valid_frames]
            return float(np.max(max_values)) if max_values else None

        elif aggregation_mode == 'individual_means':
            return [float(np.mean(f)) for f, h in valid_frames]
            
        elif aggregation_mode == 'individual_maxs':
            return [float(np.max(f)) for f, h in valid_frames]

        elif aggregation_mode == 'first_valid_mean':
             # Return mean of the first frame that is valid in the (potentially filtered) list
            return float(np.mean(valid_frames[0][0]))
        
        elif aggregation_mode == 'raw_frames':
            return valid_frames # List of (frame, header) tuples

        else:
            print(f"Aggregator: Unknown aggregation_mode '{aggregation_mode}'.")
            return None

# Example Usage (for testing)
if __name__ == '__main__':
    # This test requires a running CameraManager with connected cameras.
    # For simplicity, we'll mock it here for standalone testing of DataAggregator logic.

    class MockSenxorCamera:
        def __init__(self, port, unique_id):
            self.port = port
            self._id = unique_id
            self.is_connected = True
            self.is_streaming = True
        def get_latest_frame_and_header(self):
            # Simulate some frame data
            if self._id == 0:
                frame = np.array([[10,20],[30,40]]) + np.random.rand(2,2)
                header = {'frame_counter': 1, 'port': self.port}
            elif self._id == 1:
                frame = np.array([[50,60],[70,80]]) + np.random.rand(2,2)
                header = {'frame_counter': 1, 'port': self.port}
            else: # Simulate a camera with no data sometimes
                if np.random.rand() > 0.5:
                    frame = np.array([[5,15],[25,35]]) + np.random.rand(2,2)
                    header = {'frame_counter': 1, 'port': self.port}
                else:
                    frame, header = None, None
            return frame, header
        def __repr__(self):
            return f"MockSenxorCamera(port='{self.port}', id={self._id})"

    class MockCameraManager:
        def __init__(self, num_cameras=2):
            self.cameras = [MockSenxorCamera(f"COM{i+1}", i) for i in range(num_cameras)]
        def get_all_latest_frames_and_headers(self):
            return [cam.get_latest_frame_and_header() for cam in self.cameras]
        def get_all_cameras(self):
            return self.cameras

    print("Testing DataAggregator...")
    mock_cam_manager = MockCameraManager(num_cameras=3)
    aggregator = DataAggregator(mock_cam_manager)

    avg_temp = aggregator.get_average_of_mean_temperatures()
    print(f"Average of mean temperatures: {avg_temp}")

    max_temp_all = aggregator.get_max_temperature_from_all()
    print(f"Max temperature from all: {max_temp_all}")

    # Test get_frames_for_pid
    pid_avg_mean = aggregator.get_frames_for_pid(aggregation_mode='average_mean')
    print(f"PID data (average_mean from all): {pid_avg_mean}")

    pid_overall_max = aggregator.get_frames_for_pid(aggregation_mode='overall_max')
    print(f"PID data (overall_max from all): {pid_overall_max}")
    
    pid_individual_means = aggregator.get_frames_for_pid(aggregation_mode='individual_means')
    print(f"PID data (individual_means from all): {pid_individual_means}")

    pid_first_valid_mean = aggregator.get_frames_for_pid(aggregation_mode='first_valid_mean')
    print(f"PID data (first_valid_mean): {pid_first_valid_mean}")

    # Test with specific camera indices
    pid_avg_mean_cam0 = aggregator.get_frames_for_pid(camera_indices=[0], aggregation_mode='average_mean')
    print(f"PID data (average_mean from cam 0): {pid_avg_mean_cam0}")
    
    pid_raw_cam1 = aggregator.get_frames_for_pid(camera_indices=[1], aggregation_mode='raw_frames')
    if pid_raw_cam1 and len(pid_raw_cam1) > 0:
        f, h = pid_raw_cam1[0]
        print(f"PID data (raw_frame from cam 1): Frame shape {f.shape if f is not None else 'N/A'}, Header {h}")
    else:
        print(f"PID data (raw_frame from cam 1): No data or frame was None")

    # Test with non-existent index or camera that might return None
    pid_data_multi_idx = aggregator.get_frames_for_pid(camera_indices=[0, 2, 5], aggregation_mode='individual_means')
    print(f"PID data (individual_means from cam 0, 2, 5): {pid_data_multi_idx}")

    print("DataAggregator test finished.") 