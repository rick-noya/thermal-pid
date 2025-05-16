# Central configuration for the thermal PID controller project – now YAML-backed

import os
from typing import Any, Dict, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # Delayed import error; user must install pyyaml.

__all__ = [
    #   Public, constant-style symbols used by rest of codebase
    "STREAM_FPS",
    "DEFAULT_PORT_CAM",
    "DEFAULT_PORT_SIGGEN",
    "SIGGEN_BAUD",
    "SIGGEN_TIMEOUT",
    "HEATMAP_UPDATE_MS",
    "TREND_GRAPH_UPDATE_MS",
    "TREND_GRAPH_DEFAULT_SPAN",
    "PID_DEFAULTS",
    "HOT_SMOOTH_LEN_DEFAULT",
    "COLD_SMOOTH_LEN_DEFAULT",
    "DEFAULT_COLORMAP",
    "MAX_VOLTAGE_DEFAULT",
    "SG_DEFAULT_FREQ",
    "SG_DEFAULT_VOLTAGE",
    "VSU_INITIAL_VOLTAGE",
    "VSU_STEP_SIZE",
    "VSU_STAB_WINDOW",
    "VSU_STAB_THRESHOLD",
    "VSU_INTERVAL_MS",
    "WATER_BOIL_POINT",
    "WATER_BOIL_DWELL",
    "CAMERA_PORT_MAPPINGS",
    #   Helper
    "reload",
]

# ---------------------------------------------------------------------------
# Default values (same as legacy hard-coded ones)
# ---------------------------------------------------------------------------
STREAM_FPS: int = 15
DEFAULT_PORT_CAM: str = "COM9"
DEFAULT_PORT_SIGGEN: str = "COM8"
SIGGEN_BAUD: int = 115200
SIGGEN_TIMEOUT: float = 1.0

# UI defaults
HEATMAP_UPDATE_MS: int = 100
TREND_GRAPH_UPDATE_MS: int = 500
TREND_GRAPH_DEFAULT_SPAN: str = "1 Minute"

PID_DEFAULTS: Dict[str, Any] = dict(
    kp=1.0,
    ki=0.1,
    kd=0.05,
    setpoint=60.0,
    v_limits=(0.0, 5.0),
    sample_time=0.1,
)

# Other UI & operation defaults
HOT_SMOOTH_LEN_DEFAULT: int = 30
COLD_SMOOTH_LEN_DEFAULT: int = 30
DEFAULT_COLORMAP: str = "Viridis"
MAX_VOLTAGE_DEFAULT: float = 5.0

# Signal generator UI defaults
SG_DEFAULT_FREQ: float = 100000.0  # Hz
SG_DEFAULT_VOLTAGE: float = 1.0    # V

# Voltage Step-Up test defaults
VSU_INITIAL_VOLTAGE: float = 1.0
VSU_STEP_SIZE: float = 1.0
VSU_STAB_WINDOW: float = 10.0
VSU_STAB_THRESHOLD: float = 3.0
VSU_INTERVAL_MS: int = 100

# Water Boil test defaults
WATER_BOIL_POINT: float = 150.0  # °C
WATER_BOIL_DWELL: float = 60.0   # seconds

# Camera Port Mappings (Serial Number -> COM Port)
CAMERA_PORT_MAPPINGS: Dict[str, str] = {}

# Preserve a copy of the defaults for reload() logic
_defaults_snapshot = dict(
    STREAM_FPS=STREAM_FPS,
    DEFAULT_PORT_CAM=DEFAULT_PORT_CAM,
    DEFAULT_PORT_SIGGEN=DEFAULT_PORT_SIGGEN,
    SIGGEN_BAUD=SIGGEN_BAUD,
    SIGGEN_TIMEOUT=SIGGEN_TIMEOUT,
    HEATMAP_UPDATE_MS=HEATMAP_UPDATE_MS,
    TREND_GRAPH_UPDATE_MS=TREND_GRAPH_UPDATE_MS,
    TREND_GRAPH_DEFAULT_SPAN=TREND_GRAPH_DEFAULT_SPAN,
    PID_DEFAULTS=PID_DEFAULTS.copy(),
    HOT_SMOOTH_LEN_DEFAULT=HOT_SMOOTH_LEN_DEFAULT,
    COLD_SMOOTH_LEN_DEFAULT=COLD_SMOOTH_LEN_DEFAULT,
    DEFAULT_COLORMAP=DEFAULT_COLORMAP,
    MAX_VOLTAGE_DEFAULT=MAX_VOLTAGE_DEFAULT,
    SG_DEFAULT_FREQ=SG_DEFAULT_FREQ,
    SG_DEFAULT_VOLTAGE=SG_DEFAULT_VOLTAGE,
    VSU_INITIAL_VOLTAGE=VSU_INITIAL_VOLTAGE,
    VSU_STEP_SIZE=VSU_STEP_SIZE,
    VSU_STAB_WINDOW=VSU_STAB_WINDOW,
    VSU_STAB_THRESHOLD=VSU_STAB_THRESHOLD,
    VSU_INTERVAL_MS=VSU_INTERVAL_MS,
    WATER_BOIL_POINT=WATER_BOIL_POINT,
    WATER_BOIL_DWELL=WATER_BOIL_DWELL,
    CAMERA_PORT_MAPPINGS=CAMERA_PORT_MAPPINGS.copy(),
)


# ---------------------------------------------------------------------------
# YAML loading helpers
# ---------------------------------------------------------------------------

def _get_yaml_path(path: str | None = None) -> str:
    """Return the path to the YAML configuration file to load."""
    if path is not None:
        return path
    env_path = os.getenv("CONFIG_FILE")
    if env_path:
        return env_path
    # Default to `config.yaml` located next to this module
    return os.path.join(os.path.dirname(__file__), "config.yaml")


def _load_yaml(path: str | None = None) -> Dict[str, Any]:
    """Load YAML file, return empty dict if file or PyYAML not available."""
    if yaml is None:
        # PyYAML missing – fall back silently so application still works
        return {}

    yaml_path = _get_yaml_path(path)
    if not os.path.exists(yaml_path):
        return {}

    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ValueError("Top-level YAML structure must be a mapping/dictionary.")
            return data
    except Exception as exc:  # pragma: no cover
        # Log the error? For now, print so user sees mis-typed YAML.
        print(f"[config] WARNING: Failed to read YAML config {yaml_path}: {exc}")
        return {}


def _apply_yaml(data: Dict[str, Any]) -> None:
    """Override module-level constants with values from YAML mapping."""
    global STREAM_FPS, DEFAULT_PORT_CAM, DEFAULT_PORT_SIGGEN, SIGGEN_BAUD, SIGGEN_TIMEOUT, HEATMAP_UPDATE_MS, TREND_GRAPH_UPDATE_MS, TREND_GRAPH_DEFAULT_SPAN, PID_DEFAULTS, HOT_SMOOTH_LEN_DEFAULT, COLD_SMOOTH_LEN_DEFAULT, DEFAULT_COLORMAP, MAX_VOLTAGE_DEFAULT, SG_DEFAULT_FREQ, SG_DEFAULT_VOLTAGE, VSU_INITIAL_VOLTAGE, VSU_STEP_SIZE, VSU_STAB_WINDOW, VSU_STAB_THRESHOLD, VSU_INTERVAL_MS, WATER_BOIL_POINT, WATER_BOIL_DWELL, CAMERA_PORT_MAPPINGS

    # Camera section
    cam_cfg = data.get("camera", {})
    STREAM_FPS = int(cam_cfg.get("stream_fps", STREAM_FPS))
    DEFAULT_PORT_CAM = str(cam_cfg.get("default_port", DEFAULT_PORT_CAM))

    # Signal generator section
    sg_cfg = data.get("signal_generator", {})
    DEFAULT_PORT_SIGGEN = str(sg_cfg.get("port", DEFAULT_PORT_SIGGEN))
    SIGGEN_BAUD = int(sg_cfg.get("baud", SIGGEN_BAUD))
    SIGGEN_TIMEOUT = float(sg_cfg.get("timeout", SIGGEN_TIMEOUT))

    # PID section
    pid_cfg = data.get("pid", {})
    updated_pid_defaults: Dict[str, Any] = PID_DEFAULTS.copy()
    for key in ("kp", "ki", "kd", "setpoint"):
        if key in pid_cfg:
            updated_pid_defaults[key] = float(pid_cfg[key])
    if "v_limits" in pid_cfg:
        v_limits_raw = pid_cfg["v_limits"]
        # Accept list/tuple of len 2
        if isinstance(v_limits_raw, (list, tuple)) and len(v_limits_raw) == 2:
            updated_pid_defaults["v_limits"] = tuple(float(x) for x in v_limits_raw)
    if "sample_time" in pid_cfg:
        updated_pid_defaults["sample_time"] = float(pid_cfg["sample_time"])
    PID_DEFAULTS = updated_pid_defaults

    # UI section
    ui_cfg = data.get("ui", {})
    # Heatmap
    heatmap_cfg = ui_cfg.get("heatmap", {})
    globals()["HEATMAP_UPDATE_MS"] = int(heatmap_cfg.get("update_ms", globals()["HEATMAP_UPDATE_MS"]))

    # Trend graph
    tg_cfg = ui_cfg.get("trend_graph", {})
    globals()["TREND_GRAPH_UPDATE_MS"] = int(tg_cfg.get("update_ms", globals()["TREND_GRAPH_UPDATE_MS"]))
    globals()["TREND_GRAPH_DEFAULT_SPAN"] = str(tg_cfg.get("default_time_span", globals()["TREND_GRAPH_DEFAULT_SPAN"]))

    # Smoothing & misc UI
    smoothing_cfg = ui_cfg.get("smoothing", {})
    globals()["HOT_SMOOTH_LEN_DEFAULT"] = int(smoothing_cfg.get("hot_len", globals()["HOT_SMOOTH_LEN_DEFAULT"]))
    globals()["COLD_SMOOTH_LEN_DEFAULT"] = int(smoothing_cfg.get("cold_len", globals()["COLD_SMOOTH_LEN_DEFAULT"]))
    globals()["DEFAULT_COLORMAP"] = str(ui_cfg.get("default_colormap", globals()["DEFAULT_COLORMAP"]))
    globals()["MAX_VOLTAGE_DEFAULT"] = float(ui_cfg.get("max_voltage", globals()["MAX_VOLTAGE_DEFAULT"]))

    # Signal generator additional defaults
    if "default_frequency" in sg_cfg:
        globals()["SG_DEFAULT_FREQ"] = float(sg_cfg["default_frequency"])
    if "default_voltage" in sg_cfg:
        globals()["SG_DEFAULT_VOLTAGE"] = float(sg_cfg["default_voltage"])

    # Tests section
    tests_cfg = data.get("tests", {})
    vsu_cfg = tests_cfg.get("vsu", {})
    globals()["VSU_INITIAL_VOLTAGE"] = float(vsu_cfg.get("initial_voltage", globals()["VSU_INITIAL_VOLTAGE"]))
    globals()["VSU_STEP_SIZE"] = float(vsu_cfg.get("step_size", globals()["VSU_STEP_SIZE"]))
    globals()["VSU_STAB_WINDOW"] = float(vsu_cfg.get("stabilization_window", globals()["VSU_STAB_WINDOW"]))
    globals()["VSU_STAB_THRESHOLD"] = float(vsu_cfg.get("stabilization_threshold", globals()["VSU_STAB_THRESHOLD"]))
    globals()["VSU_INTERVAL_MS"] = int(vsu_cfg.get("interval_ms", globals()["VSU_INTERVAL_MS"]))
    # Water Boil test
    water_boil_cfg = tests_cfg.get("water_boil", {})
    globals()["WATER_BOIL_POINT"] = float(water_boil_cfg.get("boil_point", globals()["WATER_BOIL_POINT"]))
    globals()["WATER_BOIL_DWELL"] = float(water_boil_cfg.get("boil_dwell", globals()["WATER_BOIL_DWELL"]))

    # Camera Port Mappings
    cam_port_cfg = data.get("camera_ports", {})
    if isinstance(cam_port_cfg, dict):
        # Ensure keys are strings (serial numbers) and values are strings (COM ports)
        globals()["CAMERA_PORT_MAPPINGS"] = {str(k): str(v) for k, v in cam_port_cfg.items()}
    else:
        globals()["CAMERA_PORT_MAPPINGS"] = {}


# ---------------------------------------------------------------------------
# Public helper: reload()
# ---------------------------------------------------------------------------

def reload(path: str | None = None) -> None:  # noqa: D401 – simple name
    """Reload YAML configuration, overriding the in-memory constants.

    If *path* is provided, it is loaded directly; otherwise the same discovery
    logic used at import time is applied.  After loading, module-level symbols
    are updated in-place so existing imports continue to reference fresh
    values.
    """
    # Reset to hard-coded defaults first
    global STREAM_FPS, DEFAULT_PORT_CAM, DEFAULT_PORT_SIGGEN, SIGGEN_BAUD, SIGGEN_TIMEOUT, HEATMAP_UPDATE_MS, TREND_GRAPH_UPDATE_MS, TREND_GRAPH_DEFAULT_SPAN, PID_DEFAULTS, HOT_SMOOTH_LEN_DEFAULT, COLD_SMOOTH_LEN_DEFAULT, DEFAULT_COLORMAP, MAX_VOLTAGE_DEFAULT, SG_DEFAULT_FREQ, SG_DEFAULT_VOLTAGE, VSU_INITIAL_VOLTAGE, VSU_STEP_SIZE, VSU_STAB_WINDOW, VSU_STAB_THRESHOLD, VSU_INTERVAL_MS, WATER_BOIL_POINT, WATER_BOIL_DWELL, CAMERA_PORT_MAPPINGS
    STREAM_FPS = _defaults_snapshot["STREAM_FPS"]
    DEFAULT_PORT_CAM = _defaults_snapshot["DEFAULT_PORT_CAM"]
    DEFAULT_PORT_SIGGEN = _defaults_snapshot["DEFAULT_PORT_SIGGEN"]
    SIGGEN_BAUD = _defaults_snapshot["SIGGEN_BAUD"]
    SIGGEN_TIMEOUT = _defaults_snapshot["SIGGEN_TIMEOUT"]
    HEATMAP_UPDATE_MS = _defaults_snapshot["HEATMAP_UPDATE_MS"]
    TREND_GRAPH_UPDATE_MS = _defaults_snapshot["TREND_GRAPH_UPDATE_MS"]
    TREND_GRAPH_DEFAULT_SPAN = _defaults_snapshot["TREND_GRAPH_DEFAULT_SPAN"]
    PID_DEFAULTS = _defaults_snapshot["PID_DEFAULTS"].copy()
    HOT_SMOOTH_LEN_DEFAULT = _defaults_snapshot["HOT_SMOOTH_LEN_DEFAULT"]
    COLD_SMOOTH_LEN_DEFAULT = _defaults_snapshot["COLD_SMOOTH_LEN_DEFAULT"]
    DEFAULT_COLORMAP = _defaults_snapshot["DEFAULT_COLORMAP"]
    MAX_VOLTAGE_DEFAULT = _defaults_snapshot["MAX_VOLTAGE_DEFAULT"]
    SG_DEFAULT_FREQ = _defaults_snapshot["SG_DEFAULT_FREQ"]
    SG_DEFAULT_VOLTAGE = _defaults_snapshot["SG_DEFAULT_VOLTAGE"]
    VSU_INITIAL_VOLTAGE = _defaults_snapshot["VSU_INITIAL_VOLTAGE"]
    VSU_STEP_SIZE = _defaults_snapshot["VSU_STEP_SIZE"]
    VSU_STAB_WINDOW = _defaults_snapshot["VSU_STAB_WINDOW"]
    VSU_STAB_THRESHOLD = _defaults_snapshot["VSU_STAB_THRESHOLD"]
    VSU_INTERVAL_MS = _defaults_snapshot["VSU_INTERVAL_MS"]
    WATER_BOIL_POINT = _defaults_snapshot["WATER_BOIL_POINT"]
    WATER_BOIL_DWELL = _defaults_snapshot["WATER_BOIL_DWELL"]
    CAMERA_PORT_MAPPINGS = _defaults_snapshot["CAMERA_PORT_MAPPINGS"].copy()

    # Apply overrides from YAML
    _apply_yaml(_load_yaml(path))


# ---------------------------------------------------------------------------
# Initialise at import time
# ---------------------------------------------------------------------------
_apply_yaml(_load_yaml()) 