"""Unit tests for the fixtures module."""

from pytest_xdocker.process import Process


def test_process(process):
    """The process fixture should be a Process instance."""
    assert isinstance(process, Process)
