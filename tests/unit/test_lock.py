"""Unit tests for the lock module."""

import pytest

from pytest_xdocker.lock import (
    AlreadyLockedError,
    FileLock,
    MemoryLock,
    NotLockedError,
    NullLock,
)


@pytest.fixture(
    params=[
        "file",
        "memory",
    ]
)
def real_lock(tmp_path, request):
    """Produce pytest parameters for all locks."""
    if request.param == "file":
        path = tmp_path / "lockdir"
        path.mkdir()
        lockfile = path / "lockfile"
        yield FileLock(lockfile)
    elif request.param == "memory":
        yield MemoryLock()
    else:
        raise Exception(f"Unsupported lock type: {request.param}")


def test_is_locked(real_lock):
    """A lock should say it's unlocked, locked and unlocked again."""
    assert not real_lock.is_locked
    with real_lock:
        assert real_lock.is_locked

    assert not real_lock.is_locked


def test_already_locked(real_lock):
    """Locking twice should raise an AlreadyLockedError exception."""
    real_lock.lock()
    with pytest.raises(AlreadyLockedError):
        real_lock.lock()


def test_not_locked(real_lock):
    """Unlocking should raise a NotLockedError exception."""
    with pytest.raises(NotLockedError):
        real_lock.unlock()


def test_null_is_locked():
    """A null lock should never say it's locked."""
    null_lock = NullLock()
    assert not null_lock.is_locked
    null_lock.lock()
    assert not null_lock.is_locked


def test_null_lock():
    """A null lock should never raise an exception when locking."""
    null_lock = NullLock()
    null_lock.lock()
    null_lock.lock()


def test_null_unlock():
    """A null lock should never raise an exception when unlocking."""
    null_lock = NullLock()
    null_lock.unlock()
