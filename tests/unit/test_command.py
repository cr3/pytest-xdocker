"""Unit tests for the command module."""

import sys
from operator import eq, ne

import pytest

from pytest_xdocker.command import (
    Command,
    OptionalArg,
    PositionalArg,
    args_type,
    const_type,
    script_to_command,
)


@pytest.fixture
def directory(tmp_path):
    """Create e temp dir for the test."""
    path = tmp_path / "command"
    path.mkdir()
    yield path


def make_command(directory, filename, mode=0o775):
    """Create a command pointing to a file."""
    command = directory / filename
    command.touch(mode)
    return command


def make_command_subclass(**kwargs):
    """Create a class that subclasses Command."""
    return type("CommandSubclass", (Command,), kwargs)


@pytest.mark.parametrize(
    "command, op, args",
    [
        (Command("cmd"), eq, Command("cmd")),
        (Command("cmd"), eq, ["cmd"]),
        (Command("cmd"), ne, []),
        (Command("cmd").with_optionals("-o"), eq, ["cmd", "-o"]),
        (Command("cmd").with_positionals("a"), eq, ["cmd", "a"]),
        (
            Command("cmd").with_optionals("-o").with_positionals("a"),
            eq,
            ["cmd", "-o", "a"],
        ),
        (
            Command("cmd").with_positionals("a").with_optionals("-o"),
            eq,
            ["cmd", "-o", "a"],
        ),
    ],
)
def test_command_comparison(command, op, args):
    """The comparison of a command should match other commands or lists."""
    assert op(command, args)


@pytest.mark.parametrize(
    "command, expected",
    [
        (Command("cmd"), "Command(['cmd'])"),
        (Command("cmd").with_optionals("-o"), "Command(['cmd', '-o'])"),
        (Command("cmd").with_positionals("a"), "Command(['cmd', 'a'])"),
    ],
)
def test_command_repr(command, expected):
    """The representation of a command should show the class and args."""
    assert repr(command) == expected


@pytest.mark.parametrize(
    "command, string",
    [
        (Command("cmd"), "cmd"),
        (Command("cmd").with_optionals("-o"), "cmd -o"),
        (Command("cmd").with_optionals("-o", "p"), "cmd -o p"),
        (Command("cmd").with_optionals("-o", "p q"), "cmd -o 'p q'"),
        (Command("cmd").with_positionals("a"), "cmd a"),
        (Command("cmd").with_positionals("$a"), "cmd '$a'"),
        (Command("cmd").with_positionals("a", "b"), "cmd a b"),
        (Command("cmd").with_positionals("a b"), "cmd 'a b'"),
    ],
)
def test_command_str(command, string):
    """The string of a command should escape arguments when necessary."""
    assert str(command) == string


@pytest.mark.parametrize(
    "command, escape, string",
    [
        pytest.param(
            Command("cmd").with_positionals("a"),
            None,
            "cmd a",
            id="a",
        ),
        pytest.param(
            Command("cmd").with_positionals("$a"),
            lambda s: s,
            "cmd $a",
            id="$a",
        ),
        pytest.param(
            Command("cmd").with_positionals("a b"),
            lambda s: s,
            "cmd a b",
            id="a b",
        ),
    ],
)
def test_command_to_string(command, escape, string):
    """The to_string method should support overriding the escape function."""
    assert command.to_string(escape) == string


def test_command_parent():
    """The command parent should appear before the child."""
    parent = Command("parent").with_optionals("-p")
    checkout = Command("child", parent).with_optionals("-c")
    assert checkout == ["parent", "-p", "child", "-c"]


def test_command_reparent():
    """Reparenting should change the parent."""
    parent = Command("parent").with_optionals("-p")
    checkout = Command("child").reparent(parent).with_optionals("-c")
    assert checkout == ["parent", "-p", "child", "-c"]


def test_command_reparent_none():
    """Reparenting without a parent should remove the parent."""
    parent = Command("parent").with_optionals("-p")
    checkout = Command("child", parent).reparent().with_optionals("-c")
    assert checkout == ["child", "-c"]


def test_command_execute():
    """Executing a command should return the output."""
    command = Command("whoami")
    result = command.execute()
    assert result


@pytest.mark.skipif(sys.platform != "win32", reason="powershell exists on win32")
def test_command_execute_win32():
    """Executing the echo command with `powershell` should return the line."""
    command = Command("powershell").with_optionals("-NoProfile", "-c").with_positionals("echo test")
    assert command.execute() == "test\n"


@pytest.mark.skipif(sys.platform != "linux", reason="sh exists on linux")
def test_command_execute_linux():
    """Executing the echo command with `sh` should return the line."""
    command = Command("sh").with_optionals("-c").with_positionals("echo test")
    assert command.execute() == "test\n"


@pytest.mark.parametrize(
    "args, kwargs, expected",
    [
        (
            (),
            {},
            (),
        ),
        (
            (1,),
            {},
            (1,),
        ),
        (
            (1,),
            {"converter": str},
            ("1",),
        ),
        (
            ("a",),
            {},
            ("a",),
        ),
    ],
)
def test_args_type(args, kwargs, expected):
    """The args_type function should return the expected tuple or raise."""
    assert args_type(*args, **kwargs) == expected


@pytest.mark.parametrize(
    "args, expected",
    [
        (
            (1,),
            (1,),
        ),
    ],
)
def test_const_type(args, expected):
    """The const_type function should return the expected tuple."""
    assert const_type(*args) == expected


def test_optional_arg_default():
    """The default optional arg for a command should be empty."""
    subclass = make_command_subclass(with_opt=OptionalArg("--opt"))
    assert subclass("test").with_opt() == ["test", "--opt"]


def test_positional_arg_default():
    """The default positional arg for a command should be a string."""
    subclass = make_command_subclass(with_pos=PositionalArg())
    assert subclass("test").with_pos("pos") == ["test", "pos"]


@pytest.mark.skipif(sys.platform != "win32", reason="parent behavior only on win32")
def test_script_to_command_with_parent():
    """The docker-xrun command should have a Python parent."""
    command = script_to_command("docker-xrun")
    assert "python" in command.to_string()


def test_script_to_command_without_parent():
    """The python command should not have a parent."""
    command = script_to_command("python")
    assert len(list(command)) == 1


def test_script_to_command_error(unique):
    """A command that doesn't exist should raise an OSError."""
    with pytest.raises(OSError):
        script_to_command(unique("text"))
