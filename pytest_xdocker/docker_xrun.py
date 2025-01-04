"""Run a docker container with pytest xprocess.

The xprocess plugin extends pytest with options like --xkill which sends
SIGKILL to fixtures processes. The intention is for the process to stop,
so this script ensures the docker container is removed. The script is
called with the same arguments passed to docker run:

    docker-xrun alpine:3.14 sleep 600
"""

import logging
import os
import re
import sys
from contextlib import suppress
from multiprocessing import Process
from subprocess import STDOUT, CalledProcessError, check_call
from time import sleep

import psutil
from hamcrest import is_not

from pytest_xdocker.command import script_to_command
from pytest_xdocker.docker import DockerContainer, DockerRunCommand, docker
from pytest_xdocker.retry import retry

log = logging.getLogger(__name__)

docker_xrun = script_to_command("docker-xrun", DockerRunCommand).with_command


def docker_remove(name):
    """Remove a Docker container forcefully and ignore errors."""
    with open(os.devnull, "w") as devnull, suppress(CalledProcessError):
        docker.remove(name).with_force().with_volumes().execute(stderr=devnull)


def docker_run(*args):
    """Run a Docker container detached and return the container name."""
    try:
        # Use docker.command() to capture the output.
        output = docker.command("run").with_optionals("--detach").with_positionals(*args).execute(stderr=STDOUT)
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


def wait_ppid(interval=1):
    """
    Wait for a parent PID to exit (become a zombie).

    :param interval: Check the parent PID status every interval seconds.
    """
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

        container = DockerContainer(name)
        while container.status is not None:
            if container.isrunning:
                break

            sleep(interval)
            container.inspect.refresh()
        else:
            break


def monitor_ppid(name, interval=1):
    """
    Monitor a parent PID associated with a Docker container.

    Wait for the parent PID to exit and then remove the associated container.

    :param name: Name of the docker container to remove.
    :param interval: Wait for the parent PID every interval seconds.
    """
    with suppress(KeyboardInterrupt):
        wait_ppid(interval)

    docker_remove(name)
    os._exit(0)


def main(argv=sys.argv[1:]):
    """Launch and monitor a container."""
    # Check argv.
    if "--detach" in argv:
        sys.exit("Cannot pass --detach in docker arguments")

    # Pull the latest image.
    for arg in argv:
        if arg.endswith(":latest"):
            docker.pull(arg).execute()

    # Run the argv detached.
    try:
        name = retry(docker_run, *argv).until(is_not(None), tries=10)
    except AssertionError as error:
        sys.exit(str(error))

    process = Process(target=monitor_ppid, args=(name,))
    process.start()
    monitor_container(name)
    process.terminate()
    process.join()
