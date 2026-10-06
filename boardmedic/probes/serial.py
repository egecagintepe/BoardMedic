"""Serial/UART probe."""

from __future__ import annotations

from boardmedic.core.runner import CommandRunner
from boardmedic.models import SerialCapture, SerialPort


def enumerate_serial_ports() -> list[SerialPort]:
    """
    Enumerate available serial ports using pyserial.

    Returns empty list if pyserial is not available.
    Gracefully handles permission errors.
    """
    try:
        import serial.tools.list_ports as lp  # type: ignore[import]
    except ImportError:
        return []

    ports: list[SerialPort] = []
    try:
        for info in lp.comports():
            vid_str = f"{info.vid:04x}" if info.vid is not None else None
            pid_str = f"{info.pid:04x}" if info.pid is not None else None
            ports.append(SerialPort(
                port=info.device,
                description=info.description,
                hwid=info.hwid,
                manufacturer=info.manufacturer,
                vid=vid_str,
                pid=pid_str,
                is_usb=(info.vid is not None),
            ))
    except Exception:
        pass
    return ports


def capture_serial(
    port: str,
    baud: int = 115200,
    duration_seconds: float = 10.0,
    timeout_per_read: float = 1.0,
) -> SerialCapture:
    """
    Capture serial data read-only for a specified duration.

    Does NOT transmit anything.
    Returns SerialCapture with all received lines.
    """
    try:
        import serial  # type: ignore[import]
    except ImportError:
        return SerialCapture(
            port=port, baud=baud, duration_seconds=0.0,
            error="pyserial not installed"
        )

    import time
    start = time.monotonic()
    buf = ""
    lines: list[str] = []
    error: str | None = None
    timed_out = False

    try:
        with serial.Serial(port, baud, timeout=timeout_per_read) as ser:
            while True:
                elapsed = time.monotonic() - start
                if elapsed >= duration_seconds:
                    timed_out = True
                    break
                try:
                    chunk = ser.read(4096)
                    if chunk:
                        text = chunk.decode("utf-8", errors="replace")
                        buf += text
                        # Extract complete lines
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            lines.append(line.rstrip("\r"))
                except serial.SerialException as e:
                    error = str(e)
                    break
    except serial.SerialException as e:
        error = str(e)
    except PermissionError as e:
        error = f"Permission denied: {e}"
    except Exception as e:
        error = str(e)

    elapsed = time.monotonic() - start
    all_data = "\n".join(lines)
    if buf:
        all_data += buf

    return SerialCapture(
        port=port,
        baud=baud,
        duration_seconds=elapsed,
        data=all_data,
        lines=lines,
        error=error,
        timed_out=timed_out,
    )


class SerialProbe:
    """Serial/UART probe."""

    def __init__(self, runner: CommandRunner) -> None:
        self.runner = runner

    def enumerate(self) -> list[SerialPort]:
        return enumerate_serial_ports()

    def capture(
        self,
        port: str,
        baud: int,
        duration_seconds: float = 10.0,
    ) -> SerialCapture:
        return capture_serial(port, baud, duration_seconds)
