"""Unit tests for the compose module."""

from unittest.mock import Mock

import pytest

from pytest_xdocker.compose import ComposeServer, find_compose_files
from pytest_xdocker.xdocker import xdocker


def test_find_compose_files_overrides(tmp_path):
    """Finding compose files should order overrides after the base file."""
    for filename in ["compose.override.yml", "compose.yml", "other.yml"]:
        (tmp_path / filename).touch()

    result = find_compose_files(tmp_path)

    assert result == [tmp_path / "compose.yml", tmp_path / "compose.override.yml"]


def test_find_compose_files_parent(tmp_path):
    """Finding compose files should look up in parent directories."""
    (tmp_path / "docker-compose.yml").touch()
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)

    result = find_compose_files(child)

    assert result == [tmp_path / "docker-compose.yml"]


def test_find_compose_files_not_found(tmp_path):
    """Finding compose files should raise when there are none."""
    with pytest.raises(FileNotFoundError):
        find_compose_files(tmp_path)


def test_compose_server_prepare_func():
    """Preparing a compose server should start the service with up, with its project, env file and files."""
    server = ComposeServer("ready", project="p", env_file="env", compose_files=["a.yml", "b.yml"], timeout=1)

    result = server.prepare_func(Mock(basename="svc"))

    assert list(result.args) == [
        *xdocker.compose(),
        "--project-name", "p",
        "--env-file", "env",
        "--file", "a.yml",
        "--file", "b.yml",
        "up",
        "--build",
        "svc",
    ]
    assert result.pattern == "ready"
    assert result.timeout == 1


def test_compose_server_prepare_func_recreate():
    """Preparing a compose server to restart should recreate only the service."""
    server = ComposeServer("ready", project="p")
    server.recreate = True

    result = server.prepare_func(Mock(basename="svc"))

    assert list(result.args) == [
        *xdocker.compose(),
        "--project-name", "p",
        "up",
        "--build",
        "--force-recreate",
        "--no-deps",
        "svc",
    ]


def test_compose_server_project_default(pytestconfig):
    """A compose server should default its project to the root directory name."""
    server = ComposeServer("ready", process=Mock(config=pytestconfig))

    assert server.project == "pytest-xdocker"
