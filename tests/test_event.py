"""Tests for multi-shot Event."""

import threading
import time

from evo_lib.event import Event


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
        ev = Event()
        listener = ev.register(lambda v: received.append(v))
        ev.trigger(1)
        ev.unregister(listener)
        ev.trigger(2)
        assert received == [1]

    def test_wait_blocks_until_trigger(self):
        ev = Event()
        received = []
        ev.register(lambda v: received.append(v))

        def waiter():
            ev.wait()

        t = threading.Thread(target=waiter)
        t.start()
        ev.trigger(42)
        t.join(timeout=1.0)
        assert received == [42]

    def test_wait_returns_next_trigger(self):
        ev = Event()
        ev.trigger(1)  # past trigger

        received = []
        ev.register(lambda v: received.append(v))

        def waiter():
            assert ev.wait() is True  # should wait for NEXT, not past

        t = threading.Thread(target=waiter)
        t.start()
        ev.trigger(2)
        t.join(timeout=1.0)
        assert received == [2]

    def test_trigger_no_callbacks(self):
        ev = Event()
        ev.trigger(1)  # should not raise


class TestEventDebounce:
    def test_debounce_emits_only_after_stable(self):
        received = []
        ev = Event()
        debounced = ev.debounce(0.05)
        debounced.register(lambda v: received.append(v))

        # Burst of rapid events: only the last one should fire, once
        ev.trigger(1)
        ev.trigger(2)
        ev.trigger(3)
        time.sleep(0.15)
        assert received == [3]

    def test_debounce_respects_delay(self):
        received = []
        ev = Event()
        debounced = ev.debounce(0.05)
        debounced.register(lambda v: received.append(v))

        ev.trigger(1)
        # Before the delay expires, nothing should have fired yet
        time.sleep(0.02)
        assert received == []
        # After the delay, it fires
        time.sleep(0.08)
        assert received == [1]

    def test_debounce_two_stable_values(self):
        received = []
        ev = Event()
        debounced = ev.debounce(0.05)
        debounced.register(lambda v: received.append(v))

        ev.trigger("a")
        time.sleep(0.1)
        ev.trigger("b")
        time.sleep(0.1)
        assert received == ["a", "b"]
