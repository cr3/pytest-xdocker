"""Unit tests for the retry module."""

from functools import partial
from itertools import count
from unittest.mock import Mock

import pytest
from hamcrest import (
    assert_that,
    has_properties,
    is_,
    raises,
)

from pytest_xdocker.retry import (
    CatchingProbe,
    Poller,
    ProbeResult,
    UntilProbe,
    calling,
    retry,
)


class Sample:
    """Dummy class to test prettifying."""

    def __call__(self):
        """Noop."""

    def __repr__(self):
        return "<Sample>"

    @staticmethod
    def static_method():
        """Noop."""

    @classmethod
    def class_method(cls):
        """Noop."""

    def instance_method(self):
        """Noop."""


def test_calling_returns():
    """Asserting a Calling instance should match on a returned value."""
    assert_that(calling(Mock(return_value=1)), 1)


def test_calling_raises():
    """Asserting a Calling instance should match on a raised exception."""
    assert_that(calling(Mock(side_effect=KeyError)), raises(KeyError))


def test_retry_until_returns():
    """Retrying until a value should stop when matching that value."""
    assert retry(next, count()).until(1, delay=0) == 1


def test_retry_until_raises():
    """Retrying until a value should raise when not matching that value."""
    with pytest.raises(AssertionError):
        retry(next, count()).until(1, tries=0)


def test_retry_catching_never():
    """Retrying when never catching should call the function once."""
    assert retry(next, count()).catching(Exception, delay=0) == 0


def test_retry_catching_once():
    """Retrying when catching once should call the function twice."""

    def raising_func(counter):
        count = next(counter)
        if not count:
            raise Exception
        return count

    assert retry(raising_func, count()).catching(Exception, delay=0) == 1


def test_retry_catching_always():
    """Retrying when always catching should raise after trying."""

    class RetryError(Exception):
        pass

    mock_func = Mock(side_effect=RetryError)
    with pytest.raises(RetryError):
        retry(mock_func).catching(RetryError, tries=10, delay=0)

    assert mock_func.call_count == 10


def test_poller_check_sleep():
    """Polling should sleep between each probe, not after nor before."""
    mock_sleeper = Mock()
    mock_func = Mock(side_effect=partial(next, count()))
    probe = UntilProbe(mock_func, 5)
    poller = Poller(10, 0, mock_sleeper)
    poller.check(probe)
    assert mock_func.call_count == mock_sleeper.call_count + 1


@pytest.mark.parametrize(
    "func, value, result",
    [
        (Mock(return_value=0), 0, ProbeResult(True, 0)),
        (Mock(return_value=0), 1, ProbeResult(False, 0)),
    ],
)
def test_until_probe(func, value, result):
    """The UntilProbe should compare the function return to the value."""
    probe = UntilProbe(func, value)
    assert probe() == result


@pytest.mark.parametrize(
    "func, exception, pattern, matcher",
    [
        pytest.param(
            Mock(side_effect=KeyError),
            KeyError,
            "",
            has_properties(success=False, raised=is_(KeyError)),
            id="failure",
        ),
        pytest.param(
            Mock(side_effect=KeyError),
            KeyError,
            "test",
            has_properties(success=True, raised=is_(KeyError)),
            id="success with raised",
        ),
        pytest.param(
            Mock(return_value="test"),
            KeyError,
            "",
            has_properties(success=True, returned="test"),
            id="success with returned",
        ),
    ],
)
def test_catching_probe(func, exception, pattern, matcher):
    """The CatchingProbe should compare the exception to the pattern."""
    probe = CatchingProbe(func, exception, pattern)
    assert_that(probe(), matcher)


def test_catching_probe_uncaught():
    """The CatchingProbe should raise uncaught exceptions."""
    probe = CatchingProbe(Mock(side_effect=KeyError), ValueError)

    with pytest.raises(KeyError):
        probe()
