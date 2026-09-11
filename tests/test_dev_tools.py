"""Tests for the decorators in :mod:`dev_tools`."""

from __future__ import annotations

import pytest

from dev_tools import benchmark, log_calls


def test_benchmark_sync_preserves_result() -> None:
    @benchmark
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


async def test_benchmark_async_preserves_result() -> None:
    @benchmark
    async def add(a, b):
        return a + b

    assert await add(2, 3) == 5


def test_benchmark_sync_propagates_exception() -> None:
    @benchmark
    def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        boom()


async def test_benchmark_async_propagates_exception() -> None:
    @benchmark
    async def boom():
        raise ValueError("x")

    with pytest.raises(ValueError):
        await boom()


def test_log_calls_sync() -> None:
    @log_calls
    def echo(x):
        return x

    assert echo("hi") == "hi"


async def test_log_calls_async() -> None:
    @log_calls
    async def echo(x):
        return x

    assert await echo("hi") == "hi"


def test_log_calls_logs_exception(caplog) -> None:
    @log_calls
    def boom():
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        boom()


def test_benchmark_preserves_function_name() -> None:
    @benchmark
    def my_function():
        return 1

    assert my_function.__name__ == "my_function"


def test_log_calls_preserves_function_name() -> None:
    @log_calls
    def my_function():
        return 1

    assert my_function.__name__ == "my_function"
