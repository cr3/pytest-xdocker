"""Cache providers."""

import codecs
import json
from abc import ABCMeta, abstractmethod
from pathlib import Path

from attrs import define, field


def cache_encode(data):
    """Serialize cache payload."""
    return json.dumps(data).encode("utf-8")


def cache_decode(payload):
    """Deserialize cache payload."""
    return json.loads(codecs.decode(payload, "utf-8"))


class CacheError(Exception):
    """Raised with an unexpected cache error occurs."""


class Cache(metaclass=ABCMeta):
    """Base class for cache providers."""

    @abstractmethod
    def get(self, key, default):
        """Return cached value for the given key or the default."""

    @abstractmethod
    def set(self, key, value):  # noqa: A003
        """Save value for the given key."""


@define(frozen=True)
class FileCache(Cache):
    """Lightweight implementation of `pytest.cache`.

    :param path: Base path to cache directory.
    :param encode: Encoding function, defaults to `cache_encode`
    :param decode: Decoding function, defaults to `cache_decode`
    """

    _cachedir = field(converter=Path)
    encode = field(default=cache_encode)
    decode = field(default=cache_decode)

    def _get_value_path(self, key):
        path = self._cachedir / "v" / key
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def get(self, key, default):
        """Read from file."""
        path = self._get_value_path(key)
        if path.exists():
            payload = path.read_bytes()
            return self.decode(payload)
        else:
            return default

    def set(self, key, value):  # noqa: A003
        """Write to file."""
        path = self._get_value_path(key)
        payload = self.encode(value)
        path.write_bytes(payload)


@define(frozen=True)
class MemoryCache(Cache):
    """Memory cache."""

    _memory = field(factory=dict)

    def get(self, key, default):
        """Read from dict."""
        return self._memory.get(key, default)

    def set(self, key, value):  # noqa: A003
        """Write the value to dict."""
        self._memory[key] = value


@define(frozen=True)
class NullCache(Cache):
    """Null cache.

    This cache never sets a value and always gets the default value.
    """

    def get(self, key, default):
        """Noop."""
        return default

    def set(self, key, value):  # noqa: A003
        """Noop."""
