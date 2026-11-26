"""Docker compose server."""

from contextlib import contextmanager
from pathlib import Path

from pytest_xdocker.docker import DockerContainer
from pytest_xdocker.process import ProcessData, ProcessServer
from pytest_xdocker.xdocker import xdocker

COMPOSE_FILENAMES = ["docker-compose.yml", "compose.yaml", "compose.yml"]


def find_compose_files(directory):
    """Find the compose file and its overrides, looking up from directory.

    :param directory: Directory where to start looking up.
    :return: Compose files ordered so overrides come after the base file,
        ie compose.yml then compose.override.yml.
    """
    directory = Path(directory)
    for parent in [directory, *directory.parents]:
        for filename in COMPOSE_FILENAMES:
            path = parent / filename
            if path.exists():
                return sorted(parent.glob(f"{path.stem}.*"), key=lambda p: len(p.name))

    raise FileNotFoundError(f"Docker compose file not found from {directory}")


class ComposeServer(ProcessServer):
    """Server for a docker compose service.

    :param pattern: Pattern in the service output when it is ready.
    :param project: Compose project name.
    :param env_file: Optional compose env file.
    :param compose_files: Optional compose files, see `find_compose_files`.
    :param timeout: Seconds to wait for the pattern.
    """

    def __init__(self, pattern, project="test", env_file=None, compose_files=None, timeout=180, **kwargs):
        """Init."""
        super().__init__(**kwargs)
        self.pattern = pattern
        self.project = project
        self.env_file = env_file
        self.compose_files = compose_files
        self.timeout = timeout
        self.recreate = False

    def __repr__(self):
        return f"{self.__class__.__name__}(pattern={self.pattern!r}, project={self.project!r})"

    def full_name(self, name):
        """Return the container name of the service."""
        return f"{self.project}-{name}-1"

    def prepare_func(self, controldir):
        """Prepare the function to run the compose service."""
        compose = xdocker.compose().with_project_name(self.project)
        if self.env_file:
            compose = compose.with_env_file(self.env_file)
        for file in self.compose_files or []:
            compose = compose.with_file(file)

        command = compose.up(controldir.basename).with_build()
        if self.recreate:
            command = command.with_force_recreate().with_optionals("--no-deps")

        return ProcessData(self.pattern, command, timeout=self.timeout)

    @contextmanager
    def run(self, name, restart=None):
        """Run the compose service and yield its `DockerContainer`."""
        if restart is None:
            restart = self.process.restart_requested(name)
        self.recreate = bool(restart)
        with super().run(name, restart):
            yield DockerContainer(self.full_name(name), network=f"{self.project}_default")
