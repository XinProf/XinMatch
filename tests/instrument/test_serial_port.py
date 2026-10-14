"""Tests for serial-port discovery / opening (T14.4)."""

from __future__ import annotations

import pytest

from xinmatch.core.instrument import (
    SerialPortInfo,
    list_serial_ports,
    open_serial,
)


def test_list_serial_ports_returns_list_of_infos() -> None:
    ports = list_serial_ports()
    assert isinstance(ports, list)
    for p in ports:
        assert isinstance(p, SerialPortInfo)
        assert p.device  # non-empty device name
        assert p.to_dict()["device"] == p.device


def test_serial_port_info_to_dict() -> None:
    info = SerialPortInfo(device="COM3", description="USB-SERIAL", hwid="USB VID:PID")
    d = info.to_dict()
    assert d == {
        "device": "COM3",
        "description": "USB-SERIAL",
        "hwid": "USB VID:PID",
    }


def test_open_serial_missing_port_raises() -> None:
    # A deliberately bogus port must fail loudly (SerialException, an
    # OSError subclass), not silently produce a dead handle.
    with pytest.raises(OSError):
        open_serial("COM_DOES_NOT_EXIST_ZZZ", timeout=0.2)


def test_open_serial_loopback_url() -> None:
    """pyserial's loop:// URL works through our opener (real serial stack)."""
    ser = open_serial("loop://", baudrate=9600, timeout=0.5)
    try:
        # loop:// echoes writes back to the reader.
        ser.write(b"hello")
        echoed = ser.read(5)
        assert echoed == b"hello"
    finally:
        ser.close()
