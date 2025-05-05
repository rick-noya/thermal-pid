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

## Requirements

See `requirements.txt` for all dependencies.

## License

MIT License (or specify your own)
