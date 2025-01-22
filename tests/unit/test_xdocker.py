"""Unit tests for the xdocker module."""

from subprocess import CalledProcessError
from unittest.mock import Mock, patch

import pytest
from hamcrest import (
    assert_that,
    has_properties,
)

from pytest_xdocker.docker import DockerContainer
from pytest_xdocker.xdocker import (
    docker_call,
    docker_remove,
    docker_run,
    main,
    monitor_container,
)


def test_docker_remove_non_existing(unique):
    """Removing a non-existing container should not raise."""
    name = unique("text")
    docker_remove(name)


def test_docker_call(unique):
    """Calling a command other than run should raise."""
    with pytest.raises(ValueError):
        docker_call("rm")


def test_docker_run_container(unique):
    """Running a docker container should return its name."""
    name = unique("text")
    command = Mock(
        with_optionals=Mock(
            return_value=Mock(with_positionals=Mock(return_value=Mock(execute=Mock(return_value=f"{name}\n"))))
        )
    )
    result = docker_run(command=command)
    assert result == name


def test_docker_run_already_in_use(unique):
    """Running a docker container already in use should return None."""
    name = unique("text")
    command = Mock(
        with_optionals=Mock(
            side_effect=CalledProcessError(1, "", output=f'The container name "/{name}" is already in use')
        )
    )
    result = docker_run(command=command)
    assert result is None


@patch("pytest_xdocker.xdocker.DockerContainer")
@patch("pytest_xdocker.xdocker.check_call")
def test_monitor_container_normal_exit(cc_mock, dc_mock, unique):
    """When the check_call exits, if container has no status exit.

    It means the container has completed successfully.
    """
    name = unique("text")
    cc_mock.return_value = "Normal exit"

    container = Mock(DockerContainer)
    container.status = None
    dc_mock.return_value = container

    monitor_container(name, interval=0)

    dc_mock.assert_called_once_with(name)


@patch("pytest_xdocker.xdocker.DockerContainer")
@patch("pytest_xdocker.xdocker.check_call")
def test_monitor_container_follow_error(cc_mock, dc_mock, unique):
    """If the --follow command fails but container is still up, continue."""
    name = unique("text")

    cc_mock.side_effect = CalledProcessError(unique("integer"), unique("text"))

    still_running = Mock(DockerContainer)
    still_running.status = "status"
    still_running.isrunning = True
    stopped = Mock(DockerContainer)
    stopped.status = None

    dc_mock.side_effect = [still_running, stopped]

    monitor_container(name, interval=0)

    assert_that(cc_mock, has_properties(call_count=2))
    assert_that(dc_mock, has_properties(call_count=2))


@patch("pytest_xdocker.xdocker.check_call")
def test_monitor_container_any_error(cc_mock, unique):
    """If the --follow command fails but container is still up, continue."""
    cc_mock.side_effect = ValueError

    with pytest.raises(ValueError):
        monitor_container(unique("text"), interval=0)


def test_main_detach(capsys):
    """The main function should output an error when trying to detach."""
    with pytest.raises(SystemExit):
        main(["run", "--detach"])

    captured = capsys.readouterr()
    assert "Cannot pass --detach" in captured.err
