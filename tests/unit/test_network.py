"""Unit tests for the network module."""

from pytest_xdocker.network import get_open_port


def test_get_open_port_returns_different_ports():
    """Calling get_open_port twice should return different ports."""
    assert get_open_port() != get_open_port()
