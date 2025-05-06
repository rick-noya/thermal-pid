import logging
import math
from time import sleep
from datetime import datetime

try:
    from ds1054z import DS1054Z  # Requires `pip install ds1054z`
except ImportError:  # Graceful fallback if library not present
    DS1054Z = None

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ------------------------------------------------------------
# Helper utilities
# ------------------------------------------------------------

def round_up_to_nearest(value: float) -> float:
    """Round a value to the nearest 1/2/5×10^n scale used by scopes."""
    if value <= 0:
        return 1.0
    options = [1, 2, 5]
    exponent = math.floor(math.log10(value))
    scaled_value = value / (10 ** exponent)
    for option in options:
        if scaled_value <= option:
            return option * (10 ** exponent)
    return 10 ** (exponent + 1)

# ------------------------------------------------------------
# Main device class
# ------------------------------------------------------------

class Oscilloscope:
    """Wrapper around a Rigol DS1054Z oscilloscope for voltage/current/power.

    Only a subset of commands are implemented to keep integration minimal.
    """

    def __init__(self, address: str | None = None):
        self._address = address or "169.254.106.23"  # Default LAN IP of scope
        self._handle: DS1054Z | None = None
        self.device_id: str | None = None
        # Current scales (for reference)
        self.voltage_scale = 20.0  # V/div
        self.current_scale = 5.0   # A/div
        self.power_scale = 200.0   # W/div (MATH trace)
        self.timebase = 5e-6       # s/div
        # Internal storage for last measurements
        self._last_voltage = 0.0
        self._last_current = 0.0
        self._last_power = 0.0
        self._last_phase = 0.0

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def connect(self):
        if self.is_connected:
            return
        if DS1054Z is None:
            raise RuntimeError("ds1054z library not installed – cannot connect to scope.")
        try:
            self._handle = DS1054Z(self._address)
            self.device_id = self._handle.idn
            self._configure_scope()
            self.run()
            logger.info("Connected to scope at %s (id %s)", self._address, self.device_id)
        except Exception as exc:
            logger.exception("Failed to connect to scope: %s", exc)
            raise

    def disconnect(self):
        if self._handle is not None:
            try:
                self._handle.close()
            except Exception:
                pass
            finally:
                self._handle = None

    @property
    def is_connected(self) -> bool:
        return self._handle is not None

    # ------------------------------------------------------------------
    # Basic configuration
    # ------------------------------------------------------------------
    def _configure_scope(self):
        h = self._handle
        if h is None:
            return
        # CH1 – voltage
        h.write(":CHAN1:UNIT VOLT")
        h.write(":CHAN1:COUP DC")
        h.set_probe_ratio(1, 10)
        h.set_channel_offset(1, 0)
        h.set_channel_scale(1, self.voltage_scale)
        # CH2 – current
        h.write(":CHAN2:UNIT AMP")
        h.write(":CHAN2:COUP DC")
        h.set_probe_ratio(2, 10)
        h.set_channel_offset(2, 0)
        h.set_channel_scale(2, self.current_scale)
        # Math trace = CH1 × CH2 for power
        h.write(":MATH:OPER MULT")
        h.write(":MATH:SOUR1 CHAN1")
        h.write(":MATH:SOUR2 CHAN2")
        h.write(":MATH:OFFS 0")
        h.write(f":MATH:SCAL {self.power_scale}")
        # Time base
        h.timebase_scale = self.timebase
        # Trigger settings
        h.write(":TRIG:MODE EDGE")
        h.write(":TRIG:EDG:SOUR CHAN1")
        h.write(":TRIG:EDG:SLOP POS")
        h.write(":TRIG:EDG:LEV 0")
        h.write(":TRIG:SWE AUTO")
        # Phase measurement sources
        h.write(":MEAS:SET:PSA CHAN1")
        h.write(":MEAS:SET:PSB CHAN2")

    # ------------------------------------------------------------------
    # Acquisition control
    # ------------------------------------------------------------------
    def run(self):
        if self._handle:
            self._handle.run()

    def stop(self):
        if self._handle:
            self._handle.stop()

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------
    def get_outputs(self) -> tuple[float, float, float, float]:
        """Return (voltage, current, power, phase). Units: V, A, W, degrees."""
        if self._handle is None:
            return 0.0, 0.0, 0.0, 0.0
        try:
            v = self._handle.get_channel_measurement(1, "vrms") or 0.0
            i = self._handle.get_channel_measurement(2, "vrms") or 0.0
            p = self._handle.get_channel_measurement("MATH", "vrms") or 0.0
            phase = self._handle.query(":MEAS:ITEM? RPH") or 0.0
            v = float(v)
            i = float(i)
            p = float(p)
            phase = float(phase)
            self._last_voltage = v
            self._last_current = i
            self._last_power = p
            self._last_phase = phase
            return v, i, p, phase
        except Exception as exc:
            logger.debug("Error retrieving oscilloscope outputs: %s", exc)
            return self._last_voltage, self._last_current, self._last_power, self._last_phase

    # ------------------------------------------------------------------
    # Scaling helper (optional)
    # ------------------------------------------------------------------
    def scale_to_fit_screen(self, voltage: float, current: float, power: float):
        # Implementation omitted for brevity in initial integration.
        pass

# ----------------------------------------------------------------------
# Mock scope – used if ds1054z unavailable or for offline testing
# ----------------------------------------------------------------------

class MockOscilloscope(Oscilloscope):
    def __init__(self):
        super().__init__(address="mock")
        self._start_time = datetime.now()

    def connect(self):
        self.device_id = "MOCK_SCOPE"
        self._handle = True  # sentinel non-None

    def disconnect(self):
        self._handle = None

    def get_outputs(self):
        # Simple sine wave simulation for testing
        t = (datetime.now() - self._start_time).total_seconds()
        v = 10 + 5 * math.sin(2 * math.pi * 0.1 * t)
        i = 1 + 0.5 * math.sin(2 * math.pi * 0.1 * t + math.pi / 4)
        p = v * i
        phase = 45.0
        return v, i, p, phase 