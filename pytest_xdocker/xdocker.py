"""Run a docker container with pytest xprocess.

The xprocess plugin extends pytest with options like --xkill which sends
SIGKILL to fixtures processes. The intention is for the process to stop,
so this script ensures the docker container is removed. The script is
called with the same arguments passed to docker run:

    xdocker run alpine:3.14 sleep 600
"""

import logging
import os
import re
from argparse import ArgumentParser
from contextlib import suppress
from multiprocessing import Process
from subprocess import STDOUT, CalledProcessError, check_call
from time import sleep

import psutil
from hamcrest import is_not

from pytest_xdocker.command import Command, script_to_command
from pytest_xdocker.docker import (
    DockerCommand,
    DockerContainer,
    docker,
)
from pytest_xdocker.retry import retry

log = logging.getLogger(__name__)

xdocker = script_to_command("xdocker", DockerCommand)


def docker_remove(name):
    """Remove a Docker container forcefully and ignore errors."""
    with open(os.devnull, "w") as devnull, suppress(CalledProcessError):
        docker.remove(name).with_force().with_volumes().execute(stderr=devnull)


def docker_call(*args, command=docker):
    """Call Docker to run a container and return the container name."""
    args = list(args)

    # Check command.
    if args[0] == "compose":
        args.pop(0)
        command = command.compose()

    if "run" not in args:
        raise ValueError(f"Only xdocker [compose] run is supported, got: {args}")

    while args[0] != "run":
        command = command.with_optionals(args.pop(0))

    args.pop(0)
    command = Command("run", command)

    # Pull the latest image.
    for arg in args:
        if arg.endswith(":latest"):
            docker.pull(arg).execute()

    return docker_run(*args, command=command)


def docker_run(*args, command=docker.command("run")):  # noqa: B008
    """Run a Docker container detached and return the container name."""

    # Check options.
    if "--detach" in args:
        raise ValueError("Cannot pass --detach in xdocker arguments")

    try:
        output = command.with_optionals("--detach").with_positionals(*args).execute(stderr=STDOUT)
    except CalledProcessError as error:
        match = re.search(r'The container name "/(?P<name>[^"]+)" is already in use', error.output)
        if not match:
            raise

        docker_remove(match.group("name"))
        return None

    match = re.search("(?P<name>[^\r\n]+)(\r?\n)?$", output)
    if not match:
        raise Exception(f"Unpexpected docker output: {output}")

    return match.group("name")


def wait_ppid(ppid=None, interval=1):
    """
    Wait for a parent PID to exit (become a zombie).

    :param ppid: The parent PID to monitor. If None, uses os.getppid().
    :param interval: Check the parent PID status every interval seconds.
    """
    if ppid is None:
        ppid = os.getppid()
    while True:
        try:
            if psutil.Process(ppid).status() == psutil.STATUS_ZOMBIE:
                break
        except psutil.NoSuchProcess:
            break

        sleep(interval)


def monitor_container(name, interval=1):
    """
    Monitor that a Docker container exists.

    If the container is running, follow the logs. If it is stopped,
    inspect the status every interval seconds.

    :param name: Name of the docker container to monitor.
    :param interval: Check the container status every interval seconds.
    """
    while True:
        try:
            # The "since 1m" is to avoid getting the whole log from the
            # beginning when retrying after a failure because that would make
            # the xprocess.log file grow bigger and bigger everytime.
            # The first time it is called, the container has just been started
            # with --detach so its age will be less than 1 minute making this
            # equivalent to reading "from the beginning", further follows don't
            # need to go from begining, logs already be there.
            # When a failure occurs :
            # - It can be a hick-up and we lost 2 seconds of logs, see
            #   https://github.com/moby/moby/issues/41820
            # - If the container was stopped for a while and just restard there
            #   won't be older logs anyway
            # So, 1 minute is conservative.
            check_call(docker.logs(name).with_follow().with_optionals("--since", "1m"))  # noqa: S603
        except CalledProcessError:
            log.exception("--follow %s failed", name)
        except KeyboardInterrupt:
            docker_remove(name)

        container = DockerContainer(name)
        while container.status is not None:
            if container.isrunning:
                break

            sleep(interval)
            container.inspect.refresh()
        else:
            break


def monitor_ppid(name, ppid=None, interval=1):
    """
    Monitor a parent PID associated with a Docker container.

    Wait for the parent PID to exit and then remove the associated container.

    :param name: Name of the docker container to remove.
    :param ppid: The parent PID to monitor. If None, uses os.getppid().
    :param interval: Wait for the parent PID every interval seconds.
    """
    with suppress(KeyboardInterrupt):
        wait_ppid(ppid, interval)

    docker_remove(name)
    os._exit(0)


def main(argv=None):
    """Launch and monitor a container."""
    parser = ArgumentParser(add_help=False, usage="see docker")
    _, args = parser.parse_known_args(argv)

    try:
        name = retry(docker_call, *args).until(is_not(None), tries=10)
    except Exception as error:
        parser.error(str(error))

    # Pass the current PID so monitor_ppid can watch the correct parent
    # (important for Python 3.14+ where forkserver is the default)
    current_pid = os.getpid()
    process = Process(target=monitor_ppid, args=(name, current_pid))
    process.start()
    monitor_container(name)
    process.terminate()
    process.join()
