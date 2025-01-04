"""Unit tests for the process module."""

import logging
import platform

import pytest
from hamcrest import (
    assert_that,
    contains_string,
    has_item,
    has_properties,
)
from xprocess import ProcessStarter

from pytest_xdocker.process import (
    Process,
    ProcessConfig,
)


def test_process_startup_failure(tmp_path, unique):
    """If process start fails, log the content of the process."""

    def prepare_func(controldir, *args, **kwargs):
        shell = "powershell" if platform.system() == "Windows" else "sh"

        class Starter(ProcessStarter):
            args = [
                shell,
                "-c",
                'echo "Booting..."; sleep 5; echo "Ready!"',
            ]
            pattern = "Ready!"
            timeout = 3.0

        return Starter(controldir, *args, **kwargs)

    config = ProcessConfig(tmp_path)
    process = Process(config=config)
    with pytest.raises(TimeoutError):
        process.ensure(unique("text"), prepare_func)

    # Pytest adds handlers keeping records we can check.
    assert_that(
        logging.getLogger().handlers,
        has_item(
            has_properties(
                records=has_item(
                    has_properties(message=contains_string("Booting...")),
                )
            ),
        ),
    )


def test_process_preparation_failure(tmp_path, unique):
    """Failing the prep produces no log file to read, should ignore."""

    class Expected(Exception):
        """Raise me."""

    def prepare_func(*args, **kwargs):
        raise Expected()

    config = ProcessConfig(tmp_path)
    process = Process(config=config)
    with pytest.raises(Expected):
        process.ensure(unique("text"), prepare_func)
