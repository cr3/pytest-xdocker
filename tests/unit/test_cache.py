"""Unit tests for the cache module."""

from tempfile import TemporaryDirectory

import pytest

from pytest_xdocker.cache import (
    FileCache,
    MemoryCache,
    NullCache,
)


@pytest.fixture(
    params=[
        "file",
        "memory",
    ]
)
def real_cache(request):
    """Produce pytest parameters for all caches."""
    if request.param == "file":
        with TemporaryDirectory() as path:
            yield FileCache(path)
    elif request.param == "memory":
        yield MemoryCache()
    else:
        raise Exception(f"Unsupported cache type: {request.param}")


def test_cache_get_non_existing(real_cache):
    """Getting a non-existing key should return the default value."""
    assert real_cache.get("test", True)


def test_cache_get_existing(real_cache):
    """Getting an existing key should only return its value."""
    real_cache.set("test", True)
    assert real_cache.get("test", False)


def test_null_cache():
    """Getting an existing key should always return the default."""
    null_cache = NullCache()
    null_cache.set("test", True)
    assert not null_cache.get("test", False)
