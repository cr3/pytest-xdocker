"""Retry functions until a condition is met.

Here is an example of using the retry function:

    >>> from itertools import count
    >>> from hamcrest import greater_than
    >>> retry(calling(next, count())).until(greater_than(2), delay=0)
    3
"""

import re
from abc import ABCMeta, abstractmethod
from functools import wraps
from time import sleep

from attrs import define, field
from hamcrest import (
    greater_than_or_equal_to,
)

from pytest_xdocker.validators import matches


def calling(func, *args, **kwargs):
    """Defer calling a function with the given arguments.

    :param func: The function or method to be called.
    :param args: Optional positional arguments.
    :param kwargs: Optional keyword arguments.
    :return: A Calling instance which can be called later.
    """
    return Calling(func, args, kwargs)


def retry(func, *args, **kwargs):
    """Retry calling a function with the given arguments.

    :return: A Retry instance on which to specify the retry condition.
    """
    retry_func = Calling(func, args, kwargs)
    return Retry(retry_func)


def retry_catching(*args, **kwargs):
    """Retry decorator for catching exceptions."""

    def decorator(func):
        @wraps(func)
        def wrapper(*func_args, **func_kwargs):
            return retry(func, *func_args, **func_kwargs).catching(*args, **kwargs)

        return wrapper

    return decorator


NEVER = object()


@define
class Calling:
    """Function call configuration that can be repeated."""

    func = field()
    args = field(factory=tuple)
    kwargs = field(factory=dict)
    returned = field(default=NEVER)

    def __call__(self):
        """Invoke the configured function."""
        self.returned = self.func(*self.args, **self.kwargs)
        return self.returned


@define(frozen=True)
class Retry:
    """Retry the given function until the expected result."""

    func = field()

    def until(self, value, tries=30, delay=1):
        """Return a poller with a value check probe."""
        probe = UntilProbe(self.func, value)
        return Poller(tries, delay).check(probe)

    def catching(self, exception, pattern="", tries=30, delay=1):
        """Return a poller with a catching probe."""
        probe = CatchingProbe(self.func, exception, pattern)
        return Poller(tries, delay).check(probe)


@define(frozen=True)
class Poller:
    """Poller for retrying an operation."""

    tries = field(validator=matches(greater_than_or_equal_to(0)))
    delay = field(validator=matches(greater_than_or_equal_to(0)))
    sleeper = field(default=sleep)

    def check(self, probe):
        """Poll until the probe succeeds."""
        result = ProbeResult(False)
        for n in range(self.tries):
            # Only sleep in between attempts.
            if n:
                self.sleeper(self.delay)

            result = probe()
            if result:
                return result.returned
        else:
            if result.raised:
                raise result.raised
            else:
                raise AssertionError(
                    f"Polling failed after {self.tries} tries with {self.delay} seconds delay\n{probe}\n{result}"
                )


class Probe(metaclass=ABCMeta):
    """Base probe class."""

    @abstractmethod
    def __call__(self):
        """Truth value when probing."""


@define(frozen=True)
class UntilProbe(Probe):
    """Probe to expect a value from a retry."""

    func = field()
    value = field()

    def __call__(self):
        """Match the result of the function with the given value."""
        returned = self.func()
        try:
            success = self.value.matches(returned)
        except AttributeError:
            success = self.value == returned
        return ProbeResult(success, returned)

    def __str__(self):
        return f"Probing: {self.func}\n Expecting: {self.value!r}"


@define(frozen=True)
class CatchingProbe(Probe):
    """Probe to ignore an exception while retrying."""

    func = field()
    exception = field()
    pattern = field(default="")

    def __call__(self):
        """Match the exception thrown."""
        try:
            returned = self.func()
            raised = None
            success = True
        except self.exception as error:
            success = not bool(re.search(self.pattern, str(error)))
            raised = error
            returned = None

        return ProbeResult(success, returned, raised)

    def __str__(self):
        return f"Probing: {self.func}\nCatching: {self.exception}"


@define(frozen=True)
class ProbeResult:
    """Result of a probe."""

    success = field()
    returned = field(default=None)
    raised = field(default=None)

    def __bool__(self):
        return self.success

    def __nonzero__(self):
        return self.__bool__()

    def __str__(self):
        string = f"Raised: {self.raised!r}" if self.raised else f"Returned: {self.returned!r}"

        return string
