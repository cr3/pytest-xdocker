"""Integration tests for the compose module."""

from pytest_xdocker.cache import NullCache
from pytest_xdocker.compose import ComposeServer, find_compose_files
from pytest_xdocker.process import Process, ProcessConfig


def test_compose_server_run(tmp_path, unique):
    """Running a compose server should yield the running container."""
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  app:\n"
        "    image: alpine:3.21\n"
        "    command: sh -c 'echo ready; sleep 600'\n"
    )
    process = Process(config=ProcessConfig(cache=NullCache()))
    server = ComposeServer(
        "ready",
        project=unique("text"),
        compose_files=find_compose_files(tmp_path),
        process=process,
    )

    with server.run("app") as container:
        assert container.isrunning
        assert container.ip
