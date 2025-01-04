"""Test."""

from subprocess import CalledProcessError
from unittest.mock import Mock, patch

import pytest
from hamcrest import (
    assert_that,
    has_properties,
)

from pytest_xdocker.docker import DockerContainer
from pytest_xdocker.docker_xrun import (
    docker_remove,
    docker_run,
    main,
    monitor_container,
)


def test_docker_remove_non_existing(unique):
    """Removing a non-existing container should not raise."""
    name = unique("text")
    docker_remove(name)


@patch("pytest_xdocker.docker_xrun.docker")
def test_docker_run_container(docker_mock, unique):
    """Running a docker container should return its name."""
    name = unique("text")
    docker_mock.command = Mock(
        return_value=Mock(
            with_optionals=Mock(
                return_value=Mock(with_positionals=Mock(return_value=Mock(execute=Mock(return_value=f"{name}\n"))))
            )
        )
    )
    result = docker_run()
    assert result == name


@patch("pytest_xdocker.docker_xrun.docker")
def test_docker_run_already_in_use(docker_mock, unique):
    """Running a docker container already in use should return None."""
    unique("text")
    docker_mock.command = Mock(
        side_effect=CalledProcessError(1, "", output='The container name "/{name}" is already in use')
    )
    result = docker_run()
    assert result is None


@patch("pytest_xdocker.docker_xrun.docker")
def test_docker_run_error(docker_mock, unique):
    """Encountering an error when running a docker container should raise."""
    docker_mock.command = Mock(side_effect=CalledProcessError(1, "", output=""))
    with pytest.raises(CalledProcessError):
        docker_run()


@patch("pytest_xdocker.docker_xrun.DockerContainer")
@patch("pytest_xdocker.docker_xrun.check_call")
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


@patch("pytest_xdocker.docker_xrun.DockerContainer")
@patch("pytest_xdocker.docker_xrun.check_call")
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


@patch("pytest_xdocker.docker_xrun.check_call")
def test_monitor_container_any_error(cc_mock, unique):
    """If the --follow command fails but container is still up, continue."""
    cc_mock.side_effect = ValueError

    with pytest.raises(ValueError):
        monitor_container(unique("text"), interval=0)


def test_main_detach():
    """The main function should output an error when trying to detach."""
    with pytest.raises(SystemExit) as e:
        main(["--detach"])

    assert "Cannot pass --detach" in str(e.value)
