"""Module to build shell commands declaratively.

A Command instance can be used to build a shell command:

    >>> command = Command('whoami')

The command can then be executed later:

    >>> lines = command.execute().splitlines()
    >>> len(lines)
    1
"""

import logging
import os
import re
import shutil
import sys
from collections.abc import Iterable
from itertools import chain
from shlex import quote
from subprocess import check_output

from attrs import define, evolve, field


@define(eq=False, frozen=True, repr=False)
class Command(Iterable):
    """Manages a shell command."""

    _command = field(converter=str)
    _parent = field(default=iter(()))
    _positionals = field(factory=list)
    _optionals = field(factory=list)

    def __eq__(self, other):
        return list(self) == other

    def __ne__(self, other):
        return not self == other

    def __iter__(self):
        return chain(
            self._parent,
            [self._command],
            self._optionals,
            self._positionals,
        )

    def __repr__(self):
        cls = self.__class__.__name__
        args = ", ".join(repr(arg) for arg in self)
        return f"{cls}([{args}])"

    def __str__(self):
        return self.to_string()

    def to_string(self, escape=None):
        """Stringify the command."""
        if escape is None:
            escape = quote

        return " ".join(escape(part) for part in self)

    def with_positionals(self, *positionals):
        """Add positional args."""
        return evolve(self, positionals=self._positionals + list(positionals))

    def with_optionals(self, *optionals):
        """Add optional args."""
        return evolve(self, optionals=self._optionals + list(optionals))

    def reparent(self, parent=None):
        """Add a wrapping command."""
        if parent is None:
            parent = iter(())
        return evolve(self, parent=parent)

    def execute(self, **kwargs):
        """Run the command."""
        logging.info("Executing command: %s", self)
        kwargs.setdefault("universal_newlines", True)
        return check_output(self, **kwargs)  # noqa: S603


def empty_type():
    """Option arg for an undefined optional arg."""
    return args_type(min=0, max=0)


def const_type(const):
    """Option arg for a constant string."""
    return (const,)


def arg_type(arg, **kwargs):
    """Option type for a single args."""
    return args_type(arg, min=1, max=1, **kwargs)


def args_type(*args, **kwargs):
    """Option type for multiple args."""
    options = {
        "converter": lambda arg: arg,
        "min": 0,
        "max": sys.maxsize,
    }
    options.update(kwargs)

    if len(args) < options["min"]:
        raise ValueError(f"Expected at least {options['min']} args, got: {args!r}")
    if len(args) > options["max"]:
        raise ValueError(f"Expected at most {options['max']} args, got: {args!r}")

    return tuple(options["converter"](arg) for arg in args)


class OptionalArg:
    """Descriptor for optional arguments.

    :param name: Name of the option.
    :param type: Optional argument type, defaults to `empty_type`.
    :param kwargs: Optional keyword arguments passed to the type.
    """

    def __init__(self, name, type=empty_type, **kwargs):  # noqa: A002
        """Init."""
        self._name = name
        self._type = type
        self._kwargs = kwargs

    def __get__(self, obj, cls=None):
        def with_func(*args):
            values = self._type(*args, **self._kwargs)
            return obj.with_optionals(self._name, *values)

        return with_func


class PositionalArg:
    """Descriptor for positional arguments.

    :param type: Optional argument type, defaults to `arg_type`.
    :param kwargs: Optional keyword arguments passed to the type.
    """

    def __init__(self, type=arg_type, **kwargs):  # noqa: A002
        """Init."""
        self._type = type
        self._kwargs = kwargs

    def __get__(self, obj, cls=None):
        def with_func(*args):
            values = self._type(*args, **self._kwargs)
            return obj.with_positionals(*values)

        return with_func


def script_to_command(script, cls=Command):
    """
    On Windows, console scripts created as .exe should be called directly
    and those created as .cmd with Python.
    """
    path = shutil.which(script)
    if path is None:
        raise OSError(f"Script not found: {script}")

    base, ext = os.path.splitext(path)
    if re.match(r".cmd", ext, re.IGNORECASE):
        parent = Command(shutil.which("python"))
        command = cls(base, parent)
    else:
        command = cls(path)

    return command
