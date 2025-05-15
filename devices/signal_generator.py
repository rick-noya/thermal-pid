import serial
from typing import Optional
from config import DEFAULT_PORT_SIGGEN, SIGGEN_BAUD, SIGGEN_TIMEOUT


def _make_cmd(command: str) -> bytes:
    """Utility to format a command string into bytes accepted by the generator."""
    return command.encode("ascii") + b"\r\n"


class SignalGenerator:
    """Simple serial wrapper around the FY6800 style signal generator.

    The original code controlled the generator by directly writing strings to a
    PySerial object.  This class wraps that logic so other parts of the code
    only need to call high-level methods such as `set_frequency` or
    `set_voltage`.
    """

    def __init__(self, port: str | None = None, baud: int | None = None, timeout: float | None = None):
        """Create the wrapper.

        Parameters may be ``None``; when they are, the application-level
        defaults from :pyfile:`config.py` are applied.  This design lets the
        defaults be overridden by YAML without changing call sites.
        """

        self._port = port or DEFAULT_PORT_SIGGEN
        self._baud = baud or SIGGEN_BAUD
        self._timeout = timeout or SIGGEN_TIMEOUT
        self._serial: Optional[serial.Serial] = None

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    def open(self):
        if self._serial and self._serial.is_open:
            return  # already open
        try:
            self._serial = serial.Serial(self._port, self._baud, timeout=self._timeout)
        except Exception as exc:
            raise ConnectionError(f"Failed to open serial port {self._port}: {exc}") from exc

    def close(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None

    @property
    def is_open(self) -> bool:
        """Return True if the serial port is open, False otherwise."""
        return self._serial is not None and self._serial.is_open

    # ------------------------------------------------------------------
    # High-level commands
    # ------------------------------------------------------------------
    def raw_command(self, cmd: str) -> str:
        """Send a raw command string and return the response (if any)."""
        if self._serial is None or not self._serial.is_open:
            raise RuntimeError("Serial port not open – call open() first.")
        self._serial.write(_make_cmd(cmd))
        try:
            response = self._serial.readline().decode(errors="ignore").strip()
        except Exception:
            response = ""
        return response

    # ---------------------- Frequency helpers -------------------------
    def set_frequency(self, frequency_hz: int):
        """Set output frequency in Hz (integer)."""
        # According to original logic: cmd expects frequency*100 plus extra arg
        freq_val = frequency_hz * 100
        self.raw_command(f":w23={freq_val},0.")

    def increment_frequency(self, delta_hz: int = 100):
        """Increment frequency by `delta_hz`. Uses internal query to read back value if available."""
        # Not implementing query – caller must track their own state.
        self.set_frequency(self.current_frequency + delta_hz)

    def decrement_frequency(self, delta_hz: int = 100):
        self.set_frequency(max(0, self.current_frequency - delta_hz))

    # ---------------------- Voltage helpers ---------------------------
    def set_voltage(self, voltage_v: float):
        mv = int(voltage_v * 1000)
        self.raw_command(f":w25={mv}.")
        # Cache the voltage for later retrieval (e.g., for trend graph)
        self.current_voltage = voltage_v

    def output_on(self):
        self.raw_command(":w21=1.")

    def output_off(self):
        self.raw_command(":w21=0.")

    # ------------------------------------------------------------------
    # Properties – we maintain internal cache for last known settings.
    # ------------------------------------------------------------------
    @property
    def current_frequency(self) -> int:
        return getattr(self, "_freq", 0)

    @current_frequency.setter
    def current_frequency(self, value: int):
        self._freq = value

    @property
    def current_voltage(self) -> float:
        return getattr(self, "_volt", 0.0)

    @current_voltage.setter
    def current_voltage(self, v: float):
        self._volt = v 