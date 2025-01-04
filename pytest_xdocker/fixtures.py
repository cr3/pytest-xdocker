"""XProcess fixtures."""

import pytest

from pytest_xdocker.process import Process


@pytest.fixture(scope="session")
def process(request):
    """Initiliaze XProcess."""
    return Process(config=request.config)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Workaround pyest-xprocess trying to read from closed logfiles."""
    logfiles = getattr(item.config, "_extlogfiles", None)
    if logfiles is not None:  # pragma: no cover
        for name, logfile in {**logfiles}.items():
            if logfile.closed:
                del logfiles[name]
    yield


def pytest_addoption(parser):
    """Add pytest options."""
    # Extends pytest_xprocess.pytest_addoption
    group = parser.getgroup("xprocess")
    group.addoption(
        "--xrestart",
        metavar="NAME",
        nargs="*",
        help="restart named processes on the next run",
    )
