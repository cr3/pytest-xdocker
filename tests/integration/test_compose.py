"""Integration tests for the compose module."""

from functools import partial

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


def test_compose_server_keeps_dependency(tmp_path, unique):
    """Starting a service should not replace a running dependency."""
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  dependency:\n"
        "    image: alpine:3.21\n"
        "    command: sh -c 'echo dependency ready; sleep 600'\n"
        "  dependent:\n"
        "    image: alpine:3.21\n"
        "    command: sh -c 'echo dependent ready; sleep 600'\n"
        "    depends_on:\n"
        "      - dependency\n"
    )
    process = Process(config=ProcessConfig(cache=NullCache()))
    server = partial(
        ComposeServer,
        project=unique("text"),
        compose_files=find_compose_files(tmp_path),
        process=process,
    )

    with server("dependency ready").run("dependency") as dependency:
        dependency_id = dependency.inspect.get("Id")
        assert dependency_id
        with server("dependent ready").run("dependent") as dependent:
            assert dependent.isrunning
            assert dependency.isrunning
            assert dependency.inspect.get("Id") == dependency_id


def test_compose_server_after_restart(tmp_path, unique):
    """Starting a service should follow its logs across restarts."""
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  flaky:\n"
        "    image: alpine:3.21\n"
        "    restart: on-failure\n"
        "    command: sh -c 'if [ -f /once ]; then echo flaky ready; sleep 600; else touch /once; exit 1; fi'\n"
    )
    process = Process(config=ProcessConfig(cache=NullCache()))
    server = ComposeServer(
        "flaky ready",
        project=unique("text"),
        compose_files=find_compose_files(tmp_path),
        process=process,
        timeout=30,
    )

    with server.run("flaky") as container:
        assert container.isrunning
        assert container.inspect.get("RestartCount") == 1


def test_compose_server_restart(tmp_path, unique):
    """Restarting a service should recreate its container."""
    (tmp_path / "compose.yml").write_text(
        "services:\n"
        "  restartable:\n"
        "    image: alpine:3.21\n"
        "    init: true\n"
        "    command: sh -c 'echo restartable ready; sleep 600'\n"
    )
    process = Process(config=ProcessConfig(cache=NullCache()))
    server = ComposeServer(
        "restartable ready",
        project=unique("text"),
        compose_files=find_compose_files(tmp_path),
        process=process,
    )

    with server.run("restartable") as container:
        container_id = container.inspect.get("Id")

    with server.run("restartable", restart=True) as container:
        assert container.isrunning
        assert container.inspect.get("Id") != container_id
