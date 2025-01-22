"""Integration tests for the process module."""

from contextlib import contextmanager

import pytest
from yarl import URL

from pytest_xdocker.cache import NullCache
from pytest_xdocker.docker import DockerContainer, docker
from pytest_xdocker.process import Process, ProcessConfig, ProcessData, ProcessServer
from pytest_xdocker.xdocker import xdocker


class FakeServer(ProcessServer):
    """Fake server for test."""

    def prepare_func(self, controldir):
        """Configure container."""
        nc = ("sh", "-c", "while true; do nc -v -l -p 4444; done")
        command = (
            xdocker.run("alpine:3.14")
            .with_command(*nc)
            .with_name(controldir.basename)
            .with_publish(*self.get_cache_publish(controldir, 4444))
        )

        return ProcessData("listening", command)

    @contextmanager
    def run(self, name):
        """Launch container."""
        with super().run(name):
            container = DockerContainer(name)
            yield URL.build(scheme="socket", host=container.host_ip(), port=container.host_port())


@pytest.fixture(scope="session")
def fake_server(unique):
    """Produce a fake server without caching."""
    cache = NullCache()
    config = ProcessConfig(cache=cache)
    process = Process(config=config)
    server = FakeServer(process=process)
    with server.run(unique("text")) as url:
        yield url


def test_process_server_from_container(fake_server):
    """A ProcessServer should also be reacheable from other containers."""
    (docker.run("alpine:3.14").with_command("nc", fake_server.host, str(fake_server.port)).with_remove().execute())
