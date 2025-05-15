# Thermal PID Controller GUI

A modern, modular, and responsive Python GUI for controlling a Senxor/MI48 thermal camera, PID loop, and signal generator. Features live thermal imaging, real-time graphing, hardware control, and advanced visualization.

## Features

- Live thermal image with hot/cold spot overlays, smoothing, and colormap selection
- Real-time graph of max/min/avg temperature with CSV export
- Full PID and signal generator control (serial/visa)
- Responsive, modern UI with resizable panels and status bar
- Snapshot saving and loading

## Setup

1. **Clone the repository**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Connect your Senxor/MI48 camera and signal generator**
4. **Run the app:**
   ```bash
   python main.py
   ```

## Configuration

The application now looks for a YAML file at `config.yaml` (repo root) **or** a
custom path specified via the `CONFIG_FILE` environment variable. Values that
are absent fall back to sensible defaults hard-coded in the program. Example
layout:

```yaml
camera:
  stream_fps: 15
  default_port: "COM9"

signal_generator:
  port: "COM8"
  baud: 115200
  timeout: 1.0
  default_frequency: 100000
  default_voltage: 1.0

pid:
  kp: 1.0
  ki: 0.1
  kd: 0.05
  setpoint: 60.0
  v_limits: [0.0, 5.0]
  sample_time: 0.1

ui:
  heatmap:
    update_ms: 100
  trend_graph:
    update_ms: 500
    default_time_span: "1 Minute"
  smoothing:
    hot_len: 30
    cold_len: 30
  max_voltage: 5.0
  default_colormap: "Viridis"

tests:
  vsu:
    initial_voltage: 1.0
    step_size: 1.0
    stabilization_window: 10.0
    stabilization_threshold: 3.0
    interval_ms: 100
```

To try different settings without touching source code:

```bash
export CONFIG_FILE=/path/to/my_config.yaml
python main.py
```

The in-memory configuration can also be refreshed at runtime from within the
Python REPL by calling `config.reload()`.

## Usage

- Adjust PID and signal generator settings in the left panel
- View and interact with the live thermal image in the right panel
- See real-time temperature trends in the graph below
- Export graph data or save snapshots as CSV
- Drag the divider to resize panels as needed

## Project Structure

```
main.py                # Entry point
config.py              # Central configuration
ui/                    # All UI components
  app.py               # Main application frame
  control_panel.py     # PID & signal generator controls
  heatmap_view.py      # Live image and overlays
  trend_graph.py       # Real-time graph
controllers/           # PID controller logic
  pid_controller.py
devices/               # Hardware wrappers
  camera.py            # Senxor/MI48 camera
  signal_generator.py  # Signal generator serial
senxor/                # Vendor/device libraries
```

## Crash Reporting System

The application includes a robust crash reporting system that helps diagnose and troubleshoot issues:

### Features

- Detailed crash reports with system information, stack traces, and application state
- Automatic screenshot capture (when PIL is available)
- Periodic state capture to provide context for crashes
- Custom context handlers for specific operations

### Crash Report Contents

Crash reports are saved to the `logs/` directory and include:

- Basic system information (OS, Python version)
- Exception details and stack trace
- Application state at time of crash (PID settings, camera status, etc.)
- Screenshots of the application (when available)
- Recent log entries

### For Developers

The crash reporting system can be used in your code:

```python
from ui.crash_reporter import crash_reporter

# Capture additional state information
crash_reporter.capture_app_state(
    custom_data="value",
    important_info=123
)

# Use context manager for error-prone operations
with crash_reporter.error_context({"operation": "saving_file"}):
    # Code that might raise an exception
    perform_risky_operation()
```

### Logs Location

Logs and crash reports are stored in the `logs/` directory in the application root folder.

## Requirements

See `requirements.txt` for all dependencies.

## License

MIT License (or specify your own)
