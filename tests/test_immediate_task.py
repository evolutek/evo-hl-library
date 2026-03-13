"""Tests for Result, InstantResult, ErrorResult, DelayedResult, TaskRunner."""

import time

import pytest

from evo_hl.result import (
    DelayedResult,
    ErrorResult,
    InstantResult,
    TaskRunner,
)


class TestImmediateResultTask:
    def test_wait_returns_value(self):
        r = InstantResult(42)
        assert r.wait() == 42

    def test_wait_default_none(self):
        r = InstantResult()
        assert r.wait() is None

    def test_is_done(self):
        assert InstantResult(1).is_done() is True

    def test_on_complete_called_immediately(self):
        received = []
        InstantResult(42).on_complete(lambda v: received.append(v))
        assert received == [42]

    def test_on_error_not_called(self):
        received = []
        InstantResult(42).on_error(lambda e: received.append(e))
        assert received == []

    def test_chaining(self):
        received = []
        InstantResult(1).on_complete(lambda v: received.append(v)).on_error(
            lambda e: received.append(e)
        )
        assert received == [1]


class TestImmediateErrorTask:
    def test_wait_raises(self):
        r = ErrorResult(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            r.wait()

    def test_is_done(self):
        assert ErrorResult(ValueError()).is_done() is True

    def test_on_error_called_immediately(self):
        received = []
        ErrorResult(ValueError("x")).on_error(lambda e: received.append(str(e)))
        assert received == ["x"]

    def test_on_complete_not_called(self):
        received = []
        ErrorResult(ValueError()).on_complete(lambda v: received.append(v))
        assert received == []
