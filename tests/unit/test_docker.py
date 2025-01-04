"""Test."""

import os
from datetime import datetime as dt
from subprocess import CalledProcessError
from unittest.mock import Mock, patch

import pytest
from hamcrest import (
    assert_that,
    contains_inanyorder,
)

from pytest_xdocker.docker import (
    DockerContainer,
    Dockerfile,
    Dockerignore,
    DockerImage,
    DockerImageDigest,
    DockerImageId,
    DockerImageTag,
    DockerInspect,
    DockerNetworkInspect,
    DockerText,
    docker,
)


@pytest.mark.parametrize(
    "command, args",
    [
        (
            docker,
            ["docker"],
        ),
        (
            docker.with_debug(),
            ["docker", "--debug"],
        ),
        (
            docker.with_version(),
            ["docker", "--version"],
        ),
        (
            docker.build("path"),
            ["docker", "build", "path"],
        ),
        (
            docker.build("path").with_pull(),
            ["docker", "build", "--pull", "path"],
        ),
        (
            docker.build("path").with_file("file"),
            ["docker", "build", "--file", "file", "path"],
        ),
        (
            docker.build("path").with_tag(DockerImageTag("image", "tag")),
            ["docker", "build", "--tag", "image:tag", "path"],
        ),
        (
            docker.build("path").with_build_arg("var", "value"),
            ["docker", "build", "--build-arg", "var=value", "path"],
        ),
        (
            docker.exec_("name"),
            ["docker", "exec", "name"],
        ),
        (
            docker.exec_("name").with_command("command"),
            ["docker", "exec", "name", "command"],
        ),
        (
            docker.exec_("name").with_detach(),
            ["docker", "exec", "--detach", "name"],
        ),
        (
            docker.exec_("name").with_interactive(),
            ["docker", "exec", "--interactive", "name"],
        ),
        (
            docker.logs("name"),
            ["docker", "logs", "name"],
        ),
        (
            docker.logs("name").with_follow(),
            ["docker", "logs", "--follow", "name"],
        ),
        (
            docker.logs("name").with_since(dt(2000, 1, 1)),
            ["docker", "logs", "--since", "2000-01-01T00:00:00", "name"],
        ),
        (
            docker.logs("name").with_since("2000-01-01T00:00:00"),
            ["docker", "logs", "--since", "2000-01-01T00:00:00", "name"],
        ),
        (
            docker.port("name"),
            ["docker", "port", "name"],
        ),
        (
            docker.port("name").with_private_port("1234"),
            ["docker", "port", "name", "1234"],
        ),
        (
            docker.pull("image"),
            ["docker", "pull", "image"],
        ),
        (
            docker.remove("name"),
            ["docker", "rm", "name"],
        ),
        (
            docker.remove("name").with_force(),
            ["docker", "rm", "--force", "name"],
        ),
        (
            docker.remove("name").with_volumes(),
            ["docker", "rm", "--volumes", "name"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")),
            ["docker", "run", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_command("command"),
            ["docker", "run", "image:tag", "command"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_detach(),
            ["docker", "run", "--detach", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_env("key"),
            ["docker", "run", "--env", "key", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_env("key", "value"),
            ["docker", "run", "--env", "key=value", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_interactive(),
            ["docker", "run", "--interactive", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_link("name"),
            ["docker", "run", "--link", "name", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_link("name", "alias"),
            ["docker", "run", "--link", "name:alias", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_name("name"),
            ["docker", "run", "--name", "name", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_publish(1),
            ["docker", "run", "--publish", "::1", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_publish("1-2"),
            ["docker", "run", "--publish", "::1-2", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_publish(1, 2),
            ["docker", "run", "--publish", ":2:1", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_publish(1, 2, "ip"),
            ["docker", "run", "--publish", "ip:2:1", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_remove(),
            ["docker", "run", "--rm", "image:tag"],
        ),
        (
            docker.run(DockerImageTag("image", "tag")).with_workdir("workdir"),
            ["docker", "run", "--workdir", "workdir", "image:tag"],
        ),
    ],
)
def test_docker(command, args):
    """The docker options should equal the corresponding list of strings."""
    assert_that(command, args)


@pytest.mark.parametrize(
    "args, volume",
    [
        (("foo",), f"{os.path.abspath('foo')}:{os.path.abspath('foo')}"),
        (("foo", "bar"), f"{os.path.abspath('foo')}:bar"),
        (("foo", "bar", "ro"), f"{os.path.abspath('foo')}:bar:ro"),
        (("foo", "bar/baz"), f"{os.path.abspath('foo')}:bar/baz"),
    ],
)
def test_docker_run_volume(args, volume):
    """docker.run with a volume should take expected args."""
    assert list(docker.run("image").with_volume(*args)) == [
        "docker",
        "run",
        "--volume",
        volume,
        "image",
    ]


def test_container_env():
    """A container env should parse Config/Env."""
    inspect = DockerInspect(
        "name",
        {
            "Config": {
                "Env": [
                    "foo=bar",
                ],
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.env["foo"] == "bar"


def test_container_exposed_ip():
    """A container exposed IP should return NetworkSettings/IPaddress."""
    ip = "1.2.3.4"
    inspect = DockerInspect(
        "name",
        {
            "NetworkSettings": {
                "IPAddress": ip,
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.exposed_ip == ip


def test_container_exposed_port():
    """A container exposed port should return Config or ExposedPorts."""
    inspect = DockerInspect(
        "name",
        {
            "Config": {
                "ExposedPorts": {
                    "1/tcp": {},
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.exposed_port == 1


def test_container_exposed_port_error():
    """A container exposed port should raise with many ports."""
    inspect = DockerInspect(
        "name",
        {
            "Config": {
                "ExposedPorts": {
                    "1/tcp": {},
                    "2/tcp": {},
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    with pytest.raises(AssertionError):
        container.exposed_port  # noqa: B018


def test_container_exposed_ports():
    """A container exposed ports returns all Config/ExposedPorts."""
    inspect = DockerInspect(
        "name",
        {
            "Config": {
                "ExposedPorts": {
                    "1/tcp": {},
                    "2/tcp": {},
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert_that(container.exposed_ports, contains_inanyorder(1, 2))


def test_container_port_binding():
    """A container port binding returns HostConfig or PortBindings."""
    inspect = DockerInspect(
        "name",
        {
            "HostConfig": {
                "PortBindings": {
                    "1/tcp": [],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.port_binding == 1


def test_container_port_binding_error():
    """A container port binding should raise with too many ports."""
    inspect = DockerInspect(
        "name",
        {
            "HostConfig": {
                "PortBindings": {
                    "1/tcp": [],
                    "2/tcp": [],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    with pytest.raises(AssertionError):
        container.port_binding  # noqa: B018


def test_container_port_bindings():
    """A container port bindings returns all HostConfig/PortBindings."""
    inspect = DockerInspect(
        "name",
        {
            "HostConfig": {
                "PortBindings": {
                    "1/tcp": [],
                    "2/tcp": [],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert_that(container.port_bindings, contains_inanyorder(1, 2))


@pytest.mark.parametrize(
    "data, isrunning",
    [
        ({}, False),
        ({"State": {}}, False),
        ({"State": {"Running": False}}, False),
        ({"State": {"Running": True}}, True),
    ],
)
def test_container_isrunning(data, isrunning):
    """A container isrunning should return State/Running."""
    inspect = DockerInspect("name", data)
    container = DockerContainer("name", inspect)
    assert container.isrunning == isrunning


def test_container_host_ip():
    """A container host ip returns NetworkSettings/.../HostIp."""
    ip = "1.2.3.4"
    inspect = DockerInspect(
        "name",
        {
            "NetworkSettings": {
                "Ports": {
                    "1/tcp": [
                        {
                            "HostIp": ip,
                        },
                    ],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.host_ip(1) == ip


def test_container_host_ip_default():
    """A container host ip should use binding port by default."""
    ip = "1.2.3.4"
    inspect = DockerInspect(
        "name",
        {
            "HostConfig": {
                "PortBindings": {
                    "1/tcp": [],
                },
            },
            "NetworkSettings": {
                "Ports": {
                    "1/tcp": [
                        {
                            "HostIp": ip,
                        },
                    ],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.host_ip() == ip


@pytest.mark.parametrize(
    "port",
    [
        None,
        1,
    ],
)
def test_container_host_ip_none(port):
    """A container host ip should return None when not found."""
    inspect = DockerInspect("name", {})
    container = DockerContainer("name", inspect)
    assert container.host_ip(port) is None


def test_container_host_port(unique):
    """A container host port returns NetworkSettings/.../HostPort."""
    port = unique("integer")
    inspect = DockerInspect(
        "name",
        {
            "NetworkSettings": {
                "Ports": {
                    "1/tcp": [
                        {
                            "HostPort": str(port),
                        },
                    ],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.host_port(1) == port


def test_container_host_port_default(unique):
    """A container host port should use binding port by default."""
    port = unique("integer")
    inspect = DockerInspect(
        "name",
        {
            "HostConfig": {
                "PortBindings": {
                    "1/tcp": [],
                },
            },
            "NetworkSettings": {
                "Ports": {
                    "1/tcp": [
                        {
                            "HostPort": str(port),
                        },
                    ],
                },
            },
        },
    )
    container = DockerContainer("name", inspect)
    assert container.host_port() == port


@pytest.mark.parametrize(
    "port",
    [
        None,
        1,
    ],
)
def test_container_host_port_none(port):
    """A container host port should return None when not found."""
    inspect = DockerInspect("name", {})
    container = DockerContainer("name", inspect)
    assert container.host_port(port) is None


def test_inspect_data():
    """An inspect data should call refresh."""
    inspect = DockerInspect("name")
    with patch.object(inspect, "refresh") as mock_refresh:
        assert mock_refresh.call_count == 0
        inspect.data  # noqa: B018
        assert mock_refresh.call_count == 1


def test_inspect_get():
    """An inspect get should walk the keys in the data."""
    inspect = DockerInspect(
        "name",
        {
            "foo": {
                "bar": True,
            },
        },
    )
    assert inspect.get("foo", "bar") is True


def test_inspect_get_invalid():
    """An inspect get should return None for an invalid key."""
    inspect = DockerInspect("name", {})
    assert inspect.get("foo") is None


def test_inspect_command():
    """An inspect command should include docker inspect."""
    inspect = DockerInspect("name")
    assert list(inspect.command) == [
        "docker",
        "inspect",
        "name",
    ]


def test_inspect_command_exception():
    """An inspect data should be None when the command raises."""
    inspect = DockerInspect("name")
    with patch.object(DockerInspect, "command") as mock_command:
        mock_command.__get__ = Mock(return_value=Mock(execute=Mock(side_effect=CalledProcessError(1, ""))))
        assert inspect.data is None


def test_network_inspect_command():
    """A network inspect command should include docker network inspect."""
    inspect = DockerNetworkInspect("name")
    assert list(inspect.command) == [
        "docker",
        "network",
        "inspect",
        "name",
    ]


@pytest.mark.parametrize(
    "image, string",
    [
        (DockerImageId("000000000000"), "000000000000"),
        (DockerImageDigest("name", "digest"), "name@digest"),
        (DockerImageTag("name", "tag"), "name:tag"),
    ],
)
def test_image_str(image, string):
    """An image takes the form: IMAGE[:TAG|@DIGEST]."""
    assert str(image) == string


@pytest.mark.parametrize(
    "string, image",
    [
        (
            "000000000000",
            DockerImageId("000000000000"),
        ),
        (
            "name@digest",
            DockerImageDigest("name", "digest"),
        ),
        (
            "name:tag",
            DockerImageTag("name", "tag"),
        ),
        (
            "name",
            DockerImageTag("name"),
        ),
    ],
)
def test_docker_image_from_string(string, image):
    """Making an image from string should instantiate the expected class."""
    assert DockerImage.from_string(string) == image


def test_text_comment():
    """A comment begins with #."""
    text = DockerText().with_comment("comment")
    assert list(text) == ["# comment"]


def test_text_str():
    """Docker text consists of newline separated strings."""
    text = DockerText().with_line("line1").with_line("line2")
    assert str(text) == "line1\nline2\n"


def test_dockerfile_from():
    """A Dockerfile should always start with a FROM line."""
    assert list(Dockerfile("test")) == ["FROM test"]


def test_dockerfile_from_lines():
    """Creating a Dockerfile from lines should parse FROM and image."""
    dockerfile = Dockerfile.from_lines(["FROM   test", "ADD /path"])
    assert list(dockerfile) == ["FROM test", "ADD /path"]


def test_dockerfile_from_string():
    """Creating a Dockerfile from a string should split on newlines."""
    dockerfile = Dockerfile.from_string("FROM test\r\nADD /path")
    assert list(dockerfile) == ["FROM test", "ADD /path"]


def test_dockerfile_instructions():
    """A Dockerfile should contain ordered instructions."""
    dockerfile = (
        Dockerfile("test")
        .with_add("src", "dest")
        .with_copy("src", "dest")
        .with_env("key", "value")
        .with_expose(1234)
        .with_run("command")
        .with_workdir("workdir")
    )
    assert list(dockerfile) == [
        "FROM test",
        "ADD src dest",
        "COPY src dest",
        "ENV key value",
        "EXPOSE 1234",
        "RUN command",
        "WORKDIR workdir",
    ]


def test_dockerignore_pattern():
    """A .dockerignore file should containe a pattern per line."""
    dockerignore = Dockerignore().with_pattern("*").with_pattern("!test")
    assert list(dockerignore) == [
        "*",
        "!test",
    ]
