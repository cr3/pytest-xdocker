"""XProcess management."""

import logging
import sys
from abc import ABCMeta, abstractmethod
from collections import namedtuple
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import psutil
import py
from attrs import make_class
from pytest_cache import getrootdir as get_cache_root_dir
from xprocess import ProcessStarter, XProcess, XProcessInfo

from pytest_xdocker.cache import FileCache
from pytest_xdocker.lock import FileLock
from pytest_xdocker.network import get_host_ip, get_open_port

log = logging.getLogger(__name__)


def get_root_dir(config):
    """Get the root directory of the project.

    The root is assumed to contain a .git subdirectory, or config.ini.

    :param config: Pytest or Process config instance.
    """
    if config.rootdir:
        cache_root_dir = Path(config.rootdir)
    else:
        # Fallback to detecting root using pytest-cache
        compat = pytest_cache_config_compat(None, config.args, config.trace)
        cache_root_dir = Path(get_cache_root_dir(compat, ".").strpath)

    # Be careful about projects that use subprojects as roots.
    root_dirs = [cache_root_dir, cache_root_dir.parent]
    for r in root_dirs:
        if r.joinpath("config.ini").is_file() or r.joinpath(".git").exists():
            return r
    else:
        raise Exception(f"Failed to find .git in root dirs: {root_dirs}")


def get_process_dir(config, root_dir=None):
    """Get the process directory under the root directory.

    :param root_dir: Root directory, defaults to the root of the project.
    """
    if root_dir is None:
        root_dir = get_root_dir(config)

    process_dir = root_dir / ".xprocess"
    process_dir.mkdir(exist_ok=True)
    return process_dir


# Use namedtuple instead of attrs for compatibility with xprocess which
# expects an actual tuple.
class ProcessData(
    namedtuple(
        "ProcessData",
        [
            "pattern",
            "args",
            "env",
            "timeout",
        ],
    )
):
    """Representation of a process' data."""

    def __new__(cls, pattern, args, env=None, timeout=120):
        """Make the env optional."""
        return super().__new__(cls, pattern, args, env, timeout)

    def change(self, **changes):
        """Access for namedtuple _replace so that it doesn't look private."""
        return self._replace(**changes)


class ProcessConfig:
    """Lightweight process config."""

    option = None

    def __init__(self, root_dir=None, cache=None):
        """Init."""
        if root_dir is not None:
            # Backward compatibility, previous version was ensuring a
            # config.ini exists in the folder, enforced by get_root_dir
            (root_dir / "config.ini").touch()

        self.rootdir = root_dir
        self.args = []

        # Needed by ProcessServer.get_cache_publish
        if cache is None:
            cache_dir = get_root_dir(self) / ".pytest_cache"
            cache = FileCache(cache_dir)

        self.cache = cache

    def trace(self, string):
        """Write a trace log."""
        sys.stderr.write(string)


class ProcessInfo(XProcessInfo):
    """XProcessInfo with better kill/running methods."""

    def __init__(self, path, name):
        """Init."""
        super().__init__(path, name)
        self.stime_path = self.controldir.join("xprocess.STIME")

        # Work around how xprocess opens it's logpath to make
        # the resulting strings binary.
        self.logpath.open = partial(self.logpath.open, "rb")

        if self.stime_path.check() and self.stime_path.size() > 0:
            self.stime = int(self.stime_path.read())
        else:
            self.stime = None

    def kill(self):
        """Kill the process and wait for children to exit."""
        try:
            children = psutil.Process(self.pid).children()
        except psutil.NoSuchProcess:
            return 0

        status = super().terminate(kill_proc_tree=False)
        if status == 1:
            for child in children:
                child.wait()

        return status

    def isrunning(self):
        """Check if process is running."""
        if not super().isrunning():
            return False

        # Check STIME in case the PID was recycled.
        if self.stime is None:
            return False

        try:
            proc = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            return False

        if self.stime != int(proc.create_time()):
            return False

        return True


class Process(XProcess):
    """XProcess with restarting capability and extra logging."""

    def __init__(self, config=None, root_dir=None, log=None):
        """Init."""
        if config is None:
            config = ProcessConfig()
        if root_dir is None:
            root_dir = get_process_dir(config)

        root_dir = py.path.local(root_dir)
        super().__init__(config, root_dir, log)

    @property
    def root_dir(self):
        """Return the root dir, but as a snake_case property."""
        return self.rootdir

    def getinfo(self, name):
        """Get the process info based on the name."""
        return ProcessInfo(self.root_dir, name)

    def ensure(self, name, prepare_func, restart=None):
        """Ensure the container is running or restarted if requested."""
        if restart is None:
            xrestart = getattr(self.config.option, "xrestart", None)
            if xrestart is not None:
                restart = xrestart == [] or name in xrestart

        try:
            pid, log_path = super().ensure(name, prepare_func, restart)
        except Exception:
            process_output_file = Path(self.getinfo(name).logpath)
            if process_output_file.exists():
                log.warning(process_output_file.read_text())
            raise

        proc = psutil.Process(pid)
        info = self.getinfo(name)
        info.stime_path.write(str(int(proc.create_time())))

        return pid, log_path


class ProcessServer(metaclass=ABCMeta):
    """Base class for a container process."""

    def __init__(self, process=None):
        """Init."""
        if process is None:
            process = Process()

        self.process = process

    @abstractmethod
    def prepare_func(self, controldir):
        """Prepare function passed to `Process.ensure`.

        :param controldir: py.path instance of the control directory.
        :return: ProcessData used to ensure the server is running.
        """

    def get_cache_publish(self, controldir, container_ports):
        """Read from cache or define published ports."""
        cache = self.process.config.cache
        key = f"{controldir.basename}/{container_ports}"
        host_ports = cache.get(key, None)
        if host_ports is None:
            host_ports = get_open_port()
            cache.set(key, host_ports)

        return container_ports, host_ports, get_host_ip()

    @contextmanager
    def run(self, name, restart=None):
        """Run the server by name.

        :param name: Name of the process.
        :param restart: True to restart, False to keep the process,
            None to look in the process config.
        """

        def prepare_func(controldir, *args, **kwargs):
            process_data = self.prepare_func(controldir)

            class Starter(ProcessStarter):
                pattern = process_data.pattern
                args = process_data.args
                env = process_data.env
                timeout = process_data.timeout
                max_read_lines = 100000

            return Starter(controldir, *args, **kwargs)

        info = self.process.getinfo(name)
        lockfile = info.controldir.join("xprocess.lock")
        lock = FileLock(lockfile)

        with lock:
            yield self.process.ensure(name, prepare_func, restart)

        # Prevent pytest_runtest_makereport from reading a closed file handle.
        self.process.resources[0].fhandles = []
        info.terminate()


# Fake ProcessConfig that matches the config at the pytest version pytest-cache
# is expecting
pytest_cache_config_compat = make_class(
    "ProcessConfig",
    [
        "inicfg",
        "args",
        "trace",
    ],
)
