"""Locks."""

import os
from abc import ABCMeta, abstractmethod

try:
    import fcntl

    def lock(fd):
        fcntl.flock(fd, fcntl.LOCK_EX)

    def unlock(fd):
        fcntl.flock(fd, fcntl.LOCK_UN)

except ImportError:
    import msvcrt

    def lock(fd):
        msvcrt.locking(fd, msvcrt.LK_LOCK, 0)

    def unlock(fd):
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 0)


from attrs import define, field


class AlreadyLockedError(Exception):
    """Raised when a lock was already acquired."""


class NotLockedError(Exception):
    """Raised when the lock was never acquired or already released."""


class BaseLock(metaclass=ABCMeta):
    """Base class for locks."""

    @property
    @abstractmethod
    def is_locked(self):
        """Return True if lock acquired, False otherwise."""

    @abstractmethod
    def lock(self):
        """Acquire the lock.

        :raises AlreadyLockedError: If the lock was already acquired.
        """

    @abstractmethod
    def unlock(self):
        """Release the lock.

        :raises NotLockedError: If the lock was never acquired or already
            released.
        """

    def __enter__(self):
        self.lock()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()
        return False


@define
class FileLock(BaseLock):
    """Advisory file locking.

    :param lockfile: Path to the lock file.
    """

    _lockfile = field(converter=str)
    _lockfd = field(default=None)

    @property
    def is_locked(self):
        """Check if the file is locked, based on the file descriptor."""
        return self._lockfd is not None

    def lock(self):
        """See `BaseLock.lock`."""
        if self.is_locked:
            raise AlreadyLockedError("Already locked")

        self._lockfd = os.open(self._lockfile, os.O_RDWR | os.O_CREAT, 0o644)
        lock(self._lockfd)

    def unlock(self):
        """See `BaseLock.unlock`."""
        if not self.is_locked:
            raise NotLockedError("Already unlocked")

        unlock(self._lockfd)
        os.close(self._lockfd)
        self._lockfd = None


@define
class MemoryLock(BaseLock):
    """In-memory locking."""

    _is_locked = field(default=False)

    @property
    def is_locked(self):
        """Accessor for read-only private field."""
        return self._is_locked

    def lock(self):
        """See `BaseLock.lock`."""
        if self._is_locked:
            raise AlreadyLockedError("Already locked")

        self._is_locked = True

    def unlock(self):
        """See `BaseLock.unlock`."""
        if not self._is_locked:
            raise NotLockedError("Already unlocked")

        self._is_locked = False


@define
class NullLock(BaseLock):
    """Null pattern implementation."""

    @property
    def is_locked(self):
        """Return False."""
        return False

    def lock(self):
        """Do nothing."""

    def unlock(self):
        """Do nothing."""
