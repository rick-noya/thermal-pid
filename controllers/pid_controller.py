from simple_pid import PID
from devices.data_aggregator import DataAggregator
import time

class TemperaturePID(PID):
    """Extends simple_pid.PID for temperature control, optionally using a DataAggregator for input."""
    def __init__(self, kp=1.0, ki=0.1, kd=0.05, setpoint=60.0, v_limits=(0.0, 10.0),
                 data_aggregator: DataAggregator = None,
                 pid_camera_indices: list[int] = None, # e.g., [0] for first camera, None for all
                 pid_aggregation_mode: str = 'average_mean', # e.g., 'average_mean', 'overall_max'
                 sample_time=0.1):
        
        super().__init__(kp, ki, kd, setpoint=setpoint, output_limits=v_limits, sample_time=sample_time)
        
        self.data_aggregator = data_aggregator
        self.pid_camera_indices = pid_camera_indices
        self.pid_aggregation_mode = pid_aggregation_mode
        self._last_valid_input = None # Store the last known good temperature

    def set_input_source(self, aggregator: DataAggregator, 
                           camera_indices: list[int] = None, 
                           aggregation_mode: str = 'average_mean'):
        """Sets or updates the data source for the PID input."""
        if aggregator is not None and not isinstance(aggregator, DataAggregator):
            raise TypeError("aggregator must be an instance of DataAggregator or None.")
        self.data_aggregator = aggregator
        self.pid_camera_indices = camera_indices
        self.pid_aggregation_mode = aggregation_mode
        # print(f"PID input source set: Aggregator present: {self.data_aggregator is not None}, Indices: {camera_indices}, Mode: {aggregation_mode}")

    def __call__(self, current_value=None, dt=None):
        """
        Calculates PID output. 
        If a DataAggregator is configured, it fetches current_value from it.
        Otherwise, current_value must be provided as an argument.
        dt is handled by simple_pid if sample_time is set.
        """
        actual_input = None
        source_description = "direct argument"

        if self.data_aggregator is not None:
            source_description = f"aggregator (mode: {self.pid_aggregation_mode}, indices: {self.pid_camera_indices})"
            # print(f"PID: Attempting to get value from {source_description}")
            processed_value = self.data_aggregator.get_frames_for_pid(
                camera_indices=self.pid_camera_indices, 
                aggregation_mode=self.pid_aggregation_mode
            )
            # Ensure processed_value is a float, or handle None
            if isinstance(processed_value, (int, float)):
                actual_input = float(processed_value)
                self._last_valid_input = actual_input # Store last good value
                # print(f"PID: Got value {actual_input} from {source_description}")
            elif isinstance(processed_value, list) and processed_value and isinstance(processed_value[0], (int, float)):
                # If mode returns a list of numbers (e.g. individual_means), use the first one or average them?
                # For now, let's assume if a list of numbers is returned, the PID should act on the first.
                # This might need refinement based on how aggregation_mode is used.
                actual_input = float(processed_value[0])
                self._last_valid_input = actual_input
                # print(f"PID: Got value {actual_input} (from list) from {source_description}")
            else:
                # print(f"PID: No valid data from {source_description}. Using last known: {self._last_valid_input}")
                actual_input = self._last_valid_input # Use last known good value if aggregator fails
        elif current_value is not None:
            if not isinstance(current_value, (int, float)):
                # print(f"PID Error: direct current_value must be a number, got {type(current_value)}. Using last known: {self._last_valid_input}")
                actual_input = self._last_valid_input
            else:
                actual_input = float(current_value)
                self._last_valid_input = actual_input # Store it if provided directly
                # print(f"PID: Using directly provided value: {actual_input}")
        else:
            # Neither aggregator nor direct value provided, use last known if available
            # print(f"PID: No input provided. Using last known: {self._last_valid_input}")
            actual_input = self._last_valid_input

        if actual_input is None:
            # print("PID Warning: No valid input temperature available (neither from aggregator nor direct, nor last_valid). Returning 0 output.")
            # simple-pid's __call__ might raise error or behave unexpectedly if input is None and _last_output is also None initially.
            # To be safe, if we have absolutely no input, we might return 0 or min_output. Or let simple_pid handle it if it can.
            # For now, let's assume simple_pid can handle its _last_input being None if it occurs.
            # However, it is better to provide a float. If it's the very first call and no input, setpoint might be a fallback.
            return self.output_limits[0] # Return min output if no valid input ever

        # Call the parent simple_pid.__call__ method
        # print(f"PID: Calling super().__call__ with input: {actual_input}")
        return super().__call__(actual_input, dt=dt)

    def pause(self):
        self.auto_mode = False

    def resume(self):
        self.auto_mode = True # Resets integral and derivative term history upon resume
        self.reset() # simple_pid.reset() clears integral and last_input. Good for resuming.

    def update_tunings(self, kp, ki, kd):
        self.tunings = (kp, ki, kd)

    def update_setpoint(self, setpoint):
        self.setpoint = setpoint

# Example Usage (Conceptual)
if __name__ == '__main__':
    # Mock DataAggregator for testing PID controller
    class MockDataAggregator:
        def __init__(self):
            self.counter = 50
        def get_frames_for_pid(self, camera_indices, aggregation_mode):
            print(f"MockAggregator: get_frames_for_pid called with indices: {camera_indices}, mode: {aggregation_mode}")
            if aggregation_mode == 'average_mean':
                self.counter += np.random.uniform(-1, 1)
                return self.counter # Simulate a temperature reading
            elif aggregation_mode == 'overall_max':
                self.counter += np.random.uniform(-0.5, 1.5)
                return self.counter + 5 # Simulate a slightly higher max temp
            return None

    import numpy as np # For mock aggregator random

    print("Testing TemperaturePID with MockDataAggregator...")
    mock_agg = MockDataAggregator()
    
    # PID using the aggregator
    pid_with_agg = TemperaturePID(
        kp=1.2, ki=0.2, kd=0.1, setpoint=75.0, v_limits=(0, 5),
        data_aggregator=mock_agg,
        pid_camera_indices=None, # Use all cameras (as per mock_agg logic)
        pid_aggregation_mode='average_mean'
    )

    print(f"PID Initialized. Setpoint: {pid_with_agg.setpoint}, Auto_mode: {pid_with_agg.auto_mode}")

    for i in range(10):
        # PID.__call__ will use the aggregator internally
        control_voltage = pid_with_agg()
        current_temp_from_pid = pid_with_agg._last_valid_input # Accessing internal for demo
        print(f"Loop {i}: Current Temp (from agg): {current_temp_from_pid:.2f}, PID Output: {control_voltage:.2f}")
        time.sleep(0.2)

    print("\nChanging PID to use 'overall_max' mode...")
    pid_with_agg.set_input_source(mock_agg, pid_camera_indices=[0], aggregation_mode='overall_max')
    mock_agg.counter = 60 # Reset mock temp

    for i in range(5):
        control_voltage = pid_with_agg()
        current_temp_from_pid = pid_with_agg._last_valid_input
        print(f"Loop {i}: Current Temp (from agg MAX): {current_temp_from_pid:.2f}, PID Output: {control_voltage:.2f}")
        time.sleep(0.2)

    print("\nTesting TemperaturePID with direct input...")
    pid_direct = TemperaturePID(kp=1.0, ki=0.1, kd=0.05, setpoint=50.0)
    current_manual_temp = 40.0
    for i in range(5):
        current_manual_temp += np.random.uniform(0.5, 1.5) # Simulate temp change
        control_voltage = pid_direct(current_manual_temp)
        print(f"Loop {i}: Current Temp (manual): {current_manual_temp:.2f}, PID Output: {control_voltage:.2f}")
        time.sleep(0.2)
    
    print("\nTesting PID pause and resume...")
    pid_with_agg.setpoint = 65 # New setpoint
    mock_agg.counter = 60
    print(f"Setpoint: {pid_with_agg.setpoint}")
    output1 = pid_with_agg() # Run once
    print(f"Output before pause: {output1:.2f} (last temp: {pid_with_agg._last_valid_input:.2f})")
    pid_with_agg.pause()
    print(f"PID paused. Auto_mode: {pid_with_agg.auto_mode}")
    output_paused = pid_with_agg() # Should not update integral etc.
    print(f"Output while paused (should be same or based on last input if it changes): {output_paused:.2f}")
    mock_agg.counter = 50 # Simulate temp dropping while paused
    output_paused_later = pid_with_agg(mock_agg.counter) # Test direct input while paused using aggregator values
    print(f"Output while paused (direct input {mock_agg.counter}): {output_paused_later:.2f}")
    pid_with_agg.resume()
    print(f"PID resumed. Auto_mode: {pid_with_agg.auto_mode}. PID internal last_input should be reset.")
    output_resumed = pid_with_agg() # Integral term starts fresh.
    print(f"Output after resume (temp from agg {pid_with_agg._last_valid_input:.2f}): {output_resumed:.2f}")

    print("TemperaturePID test finished.") 