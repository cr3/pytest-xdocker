"""Docker tools."""

# It would be nice to replace this module with the docker-py package
# but error reporting can sometimes make it really difficult to
# troubleshoot.

import json
import logging
import os
import re
from abc import ABCMeta, abstractmethod
from collections import UserDict
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path
from subprocess import CalledProcessError, run

from attrs import define, field

from pytest_xdocker.command import (
    Command,
    OptionalArg,
    PositionalArg,
    arg_type,
    args_type,
)
from pytest_xdocker.retry import retry_catching


def docker_env_type(key, value=None):
    """Docker environment variable type.

    :param key: Environment key.
    :param value: Optional environment value.
    """
    env = key if value is None else f"{key}={value}"
    return (env,)


class DockerCommand(Command):
    """Shortcut for "docker"."""

    with_debug = OptionalArg("--debug")
    """Enable debug mode."""

    with_version = OptionalArg("--version")
    """Print version information and quit."""

    def command(self, command):
        """Return the base command."""
        return Command(command, self)

    def build(self, path):
        """Return a build command."""
        return DockerBuildCommand("build", self).with_positionals(str(path))

    def compose(self):
        """Return a compose command."""
        return DockerComposeCommand("compose", self)

    def exec_(self, name):
        """Return an exec command."""
        return DockerExecCommand("exec", self).with_positionals(name)

    def logs(self, name):
        """Return a logs command."""
        return DockerLogsCommand("logs", self).with_positionals(name)

    def port(self, name):
        """Return a port command."""
        return DockerPortCommand("port", self).with_positionals(name)

    def pull(self, image):
        """Return a pull command."""
        return DockerPullCommand("pull", self).with_positionals(str(image))

    def remove(self, name):
        """Return a rm command."""
        return DockerRemoveCommand("rm", self).with_positionals(name)

    def run(self, image):
        """Return a run command."""
        return DockerRunCommand("run", self).with_positionals(str(image))


docker = DockerCommand("docker")


class DockerRunCommand(Command):
    """Shortcut for "docker run"."""

    with_command = PositionalArg(args_type, converter=str)
    """Add command to run in the docker container.

    :param command: List of commands passed to docker.
    """

    with_detach = OptionalArg("--detach")
    """Run the container in the background."""

    with_env = OptionalArg("--env", docker_env_type)
    """Set environment variables.

    :param key: Environment key.
    :param value: Optional environment value.
    """

    with_env_file = OptionalArg("--env-file", args_type, converter=str)
    """Read in a file of environment variables.

    :param file: Path to env file.
    """

    with_interactive = OptionalArg("--interactive")
    """Keep STDIN open even if not attached."""

    with_name = OptionalArg("--name", arg_type, converter=str)
    """Assign a name to the container.

    :param name: Container name.
    """

    with_remove = OptionalArg("--rm")
    """Automatically remove the container when it exits."""

    with_workdir = OptionalArg("--workdir", arg_type, converter=str)
    """Set the working directory in the container.

    :param workdir: Working directory.
    """

    def with_link(self, name, alias=None):
        """Link to another container.

        :param name: Name of the other container.
        """
        if alias is not None:
            name = f"{name}:{alias}"

        return self.with_optionals("--link", name)

    def with_publish(self, container_ports, host_ports=None, host_ip=None):
        """Publish ports from the docker container.

        :param container_ports: Container ports, ie 1234 or 1234-1238/tcp.
        :param host_ports: Optional host ports, defaults to container ports.
        :param host_ip: Optional host IP, defaults to all interfaces.
        """
        publish = f'{host_ip or ""}:{host_ports or ""}:{container_ports}'
        return self.with_optionals("--publish", publish)

    def with_volume(self, host_src, container_dest=None, options=None):
        """Mount volumes from the host to the docker container.

        :param host_src: Source path from the host.
        :param container_dest: Destination path in the container,
            defaults to host_src.
        :param options: Comma separated list of options like [rw|ro],
            [z|Z], [[r]shared|[r]slave|[r]private], [nocopy], etc.
        """
        host_src = os.path.abspath(str(host_src))
        if container_dest is None:
            container_dest = host_src

        volume = f"{host_src}:{container_dest}"
        if options is not None:
            volume += f":{options}"

        return self.with_optionals("--volume", volume)

    def execute(self, **kwargs):
        """Run the docker command and output the progress.

        :param kwargs: Optional keyword arguments passed to run.
        """
        kwargs.setdefault("check", True)
        logging.info("Running command: %s", self)
        return run(self, **kwargs)  # noqa: S603


class DockerBuildCommand(Command):
    """Shortcut for "docker build"."""

    with_pull = OptionalArg("--pull")
    """Always attempt to pull a newer version of the image."""

    with_file = OptionalArg("--file", arg_type, converter=str)
    """Name of the Dockerfile, defaults to PATH/Dockerfile."""

    with_tag = OptionalArg("--tag", arg_type, converter=str)
    """Name and optionally a tag in the 'name:tag' format."""

    with_build_arg = OptionalArg("--build-arg", docker_env_type)
    """Configure a build ARG of the Dockerfile.

    :param key: ARG key.
    :param value: Optional value, no value will carry from envionment variable.
    """


class DockerComposeCommand(Command):
    """Shortcut for "docker compose"."""

    with_env_file = OptionalArg("--env-file", args_type, converter=str)
    """Specify an alternate environment file.

    :param file: Path to env file.
    """

    with_file = OptionalArg("--file", args_type, converter=str)
    """Compose configuration files.

    :param file: Path to configuration file.
    """

    with_project_name = OptionalArg("--project-name", arg_type, converter=str)
    """Assign a project name to the compose configuration.

    :param project_name: Project name.
    """

    def build(self, *services):
        """Return a build command."""
        return DockerComposeBuildCommand("build", self).with_positionals(*services)

    def run(self, service):
        """Return a run command."""
        return DockerComposeRunCommand("run", self).with_positionals(service)

    def up(self, *services):
        """Return an up command."""
        return DockerComposeUpCommand("up", self).with_positionals(*services)


class DockerComposeBuildCommand(Command):
    """Shortcut for "docker compose build"."""

    with_no_cache = OptionalArg("--no-cache")
    """Do not use cache when building the image."""

    with_pull = OptionalArg("--pull")
    """Always attempt to pull a newer version of the image."""


class DockerComposeRunCommand(DockerRunCommand):
    """Shortcut for "docker compose run"."""

    with_build = OptionalArg("--build")
    """Build image before starting container."""


class DockerComposeUpCommand(Command):
    """Shortcut for "docker compose up"."""

    with_build = OptionalArg("--build")
    """Build images before starting containers."""

    with_force_recreate = OptionalArg("--force-recreate")
    """Recreate containers even if their configuration and image haven't changed."""


class DockerExecCommand(Command):
    """Shortcut for "docker exec"."""

    with_command = PositionalArg(args_type, converter=str)
    """Add command to execute in the docker container.

    :param command: List ofcommands passed to docker.
    """

    with_detach = OptionalArg("--detach")
    """Execute the command in the background."""

    with_env = OptionalArg("--env", docker_env_type)
    """Set environment variables.

    :param key: Environment key.
    :param value: Optional environment value.
    """

    with_interactive = OptionalArg("--interactive")
    """Keep STDIN open even if not attached."""


class DockerLogsCommand(Command):
    """Shortcut for "docker logs"."""

    with_follow = OptionalArg("--follow")
    """Follow log output."""

    def with_since(self, timestamp):
        """Show logs since timestamp."""
        with suppress(AttributeError):
            timestamp = timestamp.isoformat()

        return self.with_optionals("--since", timestamp)


class DockerPortCommand(Command):
    """Shortcut for "docker port"."""

    with_private_port = PositionalArg(arg_type, converter=str)


class DockerPullCommand(Command):
    """Shortcut for "docker pull"."""

    @retry_catching(CalledProcessError)
    def execute(self, **kwargs):
        """Run the docker pull command and output the progress.

        Retries when failing to pull because this is usually caused by
        a recoverable network failure.

        :param kwargs: See `Command.execute`.
        """
        return super().execute(**kwargs)


class DockerRemoveCommand(Command):
    """Shortcut for "docker remove"."""

    with_force = OptionalArg("--force")
    """Force the removal of a running container (uses SIGKILL)."""

    with_volumes = OptionalArg("--volumes")
    """Remove the volumes associated with the container."""


class DockerContainer:
    """Manager a docker container."""

    def __init__(self, name, inspect=None):
        """Inint."""
        if inspect is None:
            inspect = DockerInspect(name)

        self.name = name
        self.inspect = inspect

    def _port_to_int(self, port):
        pattern = r"(?P<port>\d+)/tcp"
        match = re.match(pattern, port)
        if not match:
            raise AssertionError(f"Expecting port as {pattern}, found {port}")

        return int(match.group("port"))

    def _int_to_port(self, port):
        return f"{port}/tcp"

    @property
    def env(self):
        """Return the environment of the container as a dictionary."""
        try:
            return dict(env.split("=", 1) for env in self.inspect.get("Config", "Env"))
        except TypeError:
            return {}

    @property
    def exposed_ip(self):
        """Return the IP exposed to other containers."""
        return self.inspect.get("NetworkSettings", "IPAddress")

    @property
    def exposed_port(self):
        """Return the only port exposed to other containers."""
        if len(self.exposed_ports) != 1:
            raise AssertionError(f"Expecting one exposed port, got {self.exposed_ports}")

        return self.exposed_ports[0]

    @property
    def exposed_ports(self):
        """Return all ports exposed to other containers."""
        ports = self.inspect.get("Config", "ExposedPorts") or {}
        return [self._port_to_int(port) for port in ports]

    @property
    def port_binding(self):
        """Return the only port binding."""
        if len(self.port_bindings) != 1:
            raise AssertionError(f"Expecting one port binding, got {self.port_bindings}")

        return self.port_bindings[0]

    @property
    def port_bindings(self):
        """Return all port bindings."""
        ports = self.inspect.get("HostConfig", "PortBindings") or {}
        return [self._port_to_int(port) for port in ports]

    @property
    def isrunning(self):
        """Check if has running state."""
        return self.inspect.get("State", "Running") or False

    @property
    def status(self):
        """Get status from inspect."""
        return self.inspect.get("State", "Status")

    def host_ip(self, port=None):
        """Return the host IP accessible from the host.

        :param port: Port exposed to the host, defaults to port_binding.
        """
        if port is None:
            try:
                port = self.port_binding
            except AssertionError:
                return None

        port = self._int_to_port(port)
        return self.inspect.get("NetworkSettings", "Ports", port, 0, "HostIp")

    def host_port(self, port=None):
        """Return the host port accessible from the host.

        :param port: Port exposed to the host, defaults to port_binding.
        """
        if port is None:
            try:
                port = self.port_binding
            except AssertionError:
                return None

        port = self._int_to_port(port)
        try:
            return int(self.inspect.get("NetworkSettings", "Ports", port, 0, "HostPort"))
        except TypeError:
            return None

    def remove(self):
        """Remove the container."""
        return docker.remove(self.name)

    def start(self):
        """Start the container."""
        (docker.command("start").with_positionals(self.name).execute())

    def stop(self, wait=False):
        """Stop the container."""
        (docker.command("stop").with_positionals(self.name).execute())

        if wait:
            (docker.command("wait").with_positionals(self.name).execute())


class DockerImage(metaclass=ABCMeta):
    """Representation of a docker image."""

    @classmethod
    def from_string(cls, string):
        """Make a ``DockerImage`` based on the given `string`."""
        if "@" in string:
            return DockerImageDigest(*string.split("@"))
        elif ":" in string:
            return DockerImageTag(*string.split(":"))
        elif re.match(r"[0-9a-f]{12}$", string):
            return DockerImageId(string)
        else:
            return DockerImageTag(string)

    @abstractmethod
    def __str__(self):
        """Return the string representation of a Docker image."""

    def __eq__(self, other):
        return str(self) == other

    def __ne__(self, other):
        return not self.__eq__(other)


@define(eq=False, frozen=True)
class DockerImageId(DockerImage):
    """Representation of a docker image id."""

    identifier = field()

    def __str__(self):
        return self.identifier


@define(eq=False, frozen=True)
class DockerImageDigest(DockerImage):
    """Representation of a image:tag@digest."""

    name = field()
    digest = field()

    def __str__(self):
        return f"{self.name}@{self.digest}"


@define(eq=False, frozen=True)
class DockerImageTag(DockerImage):
    """Representation of a image:tag."""

    name = field()
    tag = field(default="latest")

    def __str__(self):
        return f"{self.name}:{self.tag}"


class DockerInspect(UserDict):
    """Reader for a docker inspect call."""

    def __init__(self, name, data=None):
        """Init."""
        self.name = name
        self._data = data

    @property
    def command(self):
        """Return the base command."""
        return docker.command("inspect").with_positionals(self.name)

    @property
    def data(self):
        """Inspect data as a dictionary."""
        if self._data is None:
            self.refresh()

        return self._data

    def get(self, *keys):
        """Read the keys from the docker inspect result."""
        value = self.data
        try:
            for key in keys:
                value = value[key]
        except (KeyError, TypeError):
            return None
        else:
            return value

    def refresh(self):
        """Refresh the inspect data."""
        with Path(os.devnull).open("w") as devnull:
            try:
                output = self.command.execute(stderr=devnull)
            except CalledProcessError:
                logging.info("Failed to inspect %s", self.name)
                self._data = None
            else:
                self._data = json.loads(output)[0]


class DockerNetworkInspect(DockerInspect):
    """Shortcut for "docker network inspect"."""

    @property
    def command(self):
        """Return the base command."""
        return docker.command("network").with_positionals("inspect", self.name)


@define
class DockerText(Iterable):
    """Tool to write a text file."""

    _lines = field(factory=list, init=False)

    def __iter__(self):
        return iter(self._lines)

    def __str__(self):
        return "\n".join(line for line in self) + "\n"

    def with_line(self, line):
        """Add line to the test."""
        self._lines.append(line)
        return self

    def with_comment(self, comment):
        """Write a comment beginning with a #.

        :param comment: String to comment.
        """
        return self.with_line(f"# {comment}")

    def write(self, path):
        """Write the text to the given path.

        :param path: Path where to write the docker text.
        """
        Path(path).write_text(self.__str__())


@define
class Dockerfile(DockerText):
    """Tool to write a Dockerfile."""

    image = field()

    def __attrs_post_init__(self):
        self.with_instruction("FROM", str(self.image))

    @classmethod
    def from_lines(cls, lines):
        """Load lines of a dockerfile."""
        instruction, image = re.split(r"\s+", lines[0], maxsplit=1)
        if instruction != "FROM":
            raise Exception(f"Expected FROM, got {instruction}")

        dockerfile = cls(image)
        for line in lines[1:]:
            dockerfile.with_line(line)

        return dockerfile

    @classmethod
    def from_path(cls, path):
        """Read a dockerfile content."""
        with Path(path).open() as f:
            lines = f.readlines()

        return cls.from_lines(lines)

    @classmethod
    def from_string(cls, string):
        """Read a dockerfile content."""
        lines = re.split(r"\r?\n", string)
        return cls.from_lines(lines)

    def with_instruction(self, instruction, *args):
        """Add instruction to the Dockerfile.

        :param instruction: Name of the instruction, eg ADD.
        :param args: Argument list for the instruction.
        """
        line = " ".join((instruction, *args))
        return self.with_line(line)

    def with_add(self, src, dest):
        """Add an Add instruction.

        The ADD instruction copies new files, directories or remote file
        URLs from <src> and adds them to the filesystem of the image at
        the path <dest>.
        """
        return self.with_instruction("ADD", src, dest)

    def with_copy(self, src, dest):
        """Add a COPY instruction.

        The COPY instruction copies new files or directories from <src>
        and adds them to the filesystem of the container at the path
        <dest>.
        """
        return self.with_instruction("COPY", src, dest)

    def with_env(self, key, value):
        """Add an ENV instruction.

        The ENV instruction sets the environment variable <key> to the
        value <value>.
        """
        return self.with_instruction("ENV", key, value)

    def with_expose(self, *ports):
        """Add an EXPOSE instruction.

        The EXPOSE instruction informs Docker that the container listens
        on the specified network ports at runtime.
        """
        return self.with_instruction("EXPOSE", *(str(port) for port in ports))

    def with_run(self, command):
        """Add a RUN instruction.

        The RUN instruction will execute any commands in a new layer on
        top of the current image and commit the results. The resulting
        committed image will be used for the next step in the Dockerfile.
        """
        return self.with_instruction("RUN", command)

    def with_workdir(self, workdir):
        """Add a WORKDIR instruction.

        The WORKDIR instruction sets the working directory for any RUN,
        CMD, ENTRYPOINT, COPY and ADD instructions that follow it in
        the Dockerfile.
        """
        return self.with_instruction("WORKDIR", workdir)


class Dockerignore(DockerText):
    """Tool to write a .dockerignore file."""

    def with_pattern(self, pattern):
        """Add a CLI instruction.

        The CLI interprets the .dockerignore file as a newline-separated
        list of patterns similar to the file globs of Unix shells.
        """
        return self.with_line(pattern)
