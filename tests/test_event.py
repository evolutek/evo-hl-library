"""Tests for multi-shot Event."""

import threading

from evo_hl.event import Event


class TestEvent:
    def test_register_and_trigger(self):
        received = []
        ev = Event()
        ev.register(lambda v: received.append(v))
        ev.trigger(42)
        assert received == [42]

    def test_multiple_triggers(self):
        received = []
        ev = Event()
        ev.register(lambda v: received.append(v))
        ev.trigger(1)
        ev.trigger(2)
        ev.trigger(3)
        assert received == [1, 2, 3]

    def test_multiple_callbacks(self):
        a, b = [], []
        ev = Event()
        ev.register(lambda v: a.append(v))
        ev.register(lambda v: b.append(v))
        ev.trigger(99)
        assert a == [99]
        assert b == [99]

    def test_unregister(self):
        received = []
        cb = lambda v: received.append(v)
        ev = Event()
        ev.register(cb)
        ev.trigger(1)
        ev.unregister(cb)
        ev.trigger(2)
        assert received == [1]

    def test_wait_blocks_until_trigger(self):
        ev = Event()
        result = []

        def waiter():
            val = ev.wait()
            result.append(val)

        t = threading.Thread(target=waiter)
        t.start()
        ev.trigger(42)
        t.join(timeout=1.0)
        assert result == [42]

    def test_wait_returns_next_trigger(self):
        ev = Event()
        ev.trigger(1)  # past trigger

        result = []

        def waiter():
            val = ev.wait()  # should wait for NEXT, not past
            result.append(val)

        t = threading.Thread(target=waiter)
        t.start()
        ev.trigger(2)
        t.join(timeout=1.0)
        assert result == [2]

    def test_trigger_no_callbacks(self):
        ev = Event()
        ev.trigger(1)  # should not raise
