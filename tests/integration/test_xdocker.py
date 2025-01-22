"""Integraion tests for the xdocker module."""

from contextlib import contextmanager, suppress
from subprocess import CalledProcessError

import psutil
from hamcrest import equal_to_ignoring_whitespace

from pytest_xdocker.docker import DockerContainer, DockerInspect, docker
from pytest_xdocker.process import (
    Process,
    ProcessConfig,
    ProcessStarter,
)
from pytest_xdocker.retry import retry
from pytest_xdocker.xdocker import xdocker


@contextmanager
def run_process(name, directory, **data):
    """Run a process with cleanup."""

    class Starter(ProcessStarter):
        args = data.get("args")
        pattern = data.get("pattern")

    config = ProcessConfig(directory)
    process = Process(config)
    pid, _ = process.ensure(name, Starter)

    parent = psutil.Process(pid)
    children = parent.children()

    yield process.getinfo(name)

    with suppress(CalledProcessError):
        docker.remove(name).with_force().execute()

    for p in [parent, *children]:
        with suppress(psutil.NoSuchProcess):
            p.kill()
            p.wait()


@contextmanager
def sleep_process(name, directory, seconds=60):
    """Run a process that sleeps."""
    args = (
        xdocker.run("alpine:3.14")
        .with_name(name)
        .with_command(
            "sh",
            "-c",
            " && ".join([
                "echo started",
                f"sleep {seconds}",
            ]),
        )
    )
    with run_process(name, directory, args=args, pattern="started") as info:
        yield info


def test_kill_parent(tmp_path, unique):
    """Killing the parent should kill the children and remove the container."""
    name = unique("text")
    with sleep_process(name, tmp_path) as info:
        children = psutil.Process(info.pid).children()

        # Kill the parent.
        info.kill()

        # Detect the container is removed.
        retry(DockerInspect(name).get).until(None)

        for child in children:
            retry(child.is_running).until(False)


def test_remove_container(tmp_path, unique):
    """Removing the container should kill the parent and the children."""
    name = unique("text")
    with sleep_process(name, tmp_path) as info:
        parent = psutil.Process(info.pid)
        children = parent.children()

        # Remove the container.
        retry(docker.remove(name).with_force().execute).until(equal_to_ignoring_whitespace(name))

        # Detect the process exited.
        with suppress(psutil.NoSuchProcess):
            retry(parent.status).until(psutil.STATUS_ZOMBIE)

        for child in children:
            retry(child.is_running).until(False)


def test_stop_container(tmp_path, unique):
    """Stopping the container should not kill the parent."""
    name = unique("text")
    with sleep_process(name, tmp_path) as info:
        parent = psutil.Process(info.pid)

        container = DockerContainer(name)
        container.stop()
        assert parent.status() != psutil.STATUS_ZOMBIE

        container.start()
        assert parent.status() != psutil.STATUS_ZOMBIE
