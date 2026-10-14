"""Serial-port instrument support (T14.4).

Pure-core layer: port discovery and safe serial opening.  No GUI, no
data-collection logic here (see :mod:`xinmatch.core.instrument.collector`).

pyserial is an optional runtime dependency for this module; importing the
module does **not** require it (``serial`` is imported lazily inside the
functions), so the rest of XinMatch keeps working on machines without a
serial stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["SerialPortInfo", "list_serial_ports", "open_serial"]


@dataclass(frozen=True)
class SerialPortInfo:
    """A detected serial port."""

    device: str
    description: str = ""
    hwid: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "device": self.device,
            "description": self.description,
            "hwid": self.hwid,
        }


def _serial():
    """Lazy import pyserial; raise a clear error when unavailable."""
    try:
        import serial  # noqa: PLC0415 — optional dependency
    except ImportError as exc:  # pragma: no cover — env-dependent
        raise RuntimeError(
            "pyserial is required for serial instrument support; "
            "install it with: pip install pyserial"
        ) from exc
    return serial


def list_serial_ports() -> list[SerialPortInfo]:
    """Enumerate serial ports visible to the OS.

    Uses ``serial.tools.list_ports`` (COMx on Windows, /dev/tty* on
    POSIX).  On platforms where the tool is unavailable it returns an
    empty list rather than raising.
    """
    _serial()  # raises a clear error when pyserial is missing
    try:
        from serial.tools import list_ports  # noqa: PLC0415
    except ImportError:  # pragma: no cover — env-dependent
        logger.warning("pyserial list_ports unavailable; returning []")
        return []
    ports: list[SerialPortInfo] = []
    for p in list_ports.comports():
        ports.append(
            SerialPortInfo(
                device=p.device,
                description=p.description or "",
                hwid=p.hwid or "",
            )
        )
    return ports


def open_serial(
    port: str,
    baudrate: int = 9600,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1.0,
    timeout: float | None = 1.0,
    **kwargs: Any,
):
    """Open a serial port for reading.

    Parameters mirror pyserial's ``serial.Serial``: ``parity`` is one of
    "N"/"E"/"O"/"M"/"S", ``stopbits`` 1/1.5/2.  A non-zero *timeout* keeps
    ``readline`` from blocking forever when the instrument is silent.
    """
    serial = _serial()
    return serial.serial_for_url(
        port,
        baudrate=baudrate,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
        timeout=timeout,
        **kwargs,
    )
