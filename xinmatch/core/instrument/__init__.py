"""Serial instrument support (T14.4): port discovery + data collection."""

from xinmatch.core.instrument.collector import (
    DataPoint,
    SerialCollector,
    SerialConfig,
    parse_point,
)
from xinmatch.core.instrument.serial_port import (
    SerialPortInfo,
    list_serial_ports,
    open_serial,
)

__all__ = [
    "DataPoint",
    "SerialCollector",
    "SerialConfig",
    "SerialPortInfo",
    "list_serial_ports",
    "open_serial",
    "parse_point",
]
