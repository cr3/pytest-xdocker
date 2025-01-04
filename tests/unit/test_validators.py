"""Unit tests for the validators module."""

import pytest
from hamcrest import equal_to

from pytest_xdocker.validators import matches


def test_matches_success():
    """Nothing happens if it matches."""
    m = matches(equal_to(0))
    m(None, None, 0)


def test_matches_failure():
    """Raises `AssertionError` if it doesn't match."""
    m = matches(equal_to(0))
    with pytest.raises(AssertionError):
        m(None, None, 1)


def test_matches_repr():
    """Returns a useful representation."""
    m = matches(equal_to(0))
    assert repr(m) == "matches <<0>>"
