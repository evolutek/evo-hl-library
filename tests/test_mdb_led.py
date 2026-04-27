"""Tests for MdbLed (state machine + animator) on the virtual backend.

The animator thread is disabled in most tests via ``auto_start_animator=False``
so each frame can be inspected deterministically with ``tick()``. A separate
test exercises the live thread to confirm wakeup signalling actually works.
"""

import threading
import time

import pytest

from evo_lib.drivers.led_strip.mdb_led import (
    MdbLed,
    MdbLedState,
    MdbLedVirtual,
)
from evo_lib.logger import Logger


@pytest.fixture
def logger():
    return Logger("test")


@pytest.fixture
def strip(logger):
    s = MdbLedVirtual(
        name="mdb",
        logger=logger,
        num_pixels=4,
        loading_chase_length=1,  # legacy width — most rendering tests assume single-pixel chase
        auto_start_animator=False,
    )
    s.init().wait()
    yield s
    s.close()


@pytest.fixture
def wide_strip(logger):
    """Strip large enough to observe a 5-pixel chase without wrap."""
    s = MdbLedVirtual(
        name="mdb_wide",
        logger=logger,
        num_pixels=12,
        loading_chase_length=5,
        auto_start_animator=False,
    )
    s.init().wait()
    yield s
    s.close()


def _all_pixels_equal(frame, expected, tol=1 / 255 + 1e-9):
    er, eg, eb = expected
    for r, g, b in frame:
        assert abs(r - er) < tol
        assert abs(g - eg) < tol
        assert abs(b - eb) < tol


class TestRendering:
    """One test per branch of ``_render_frame``."""

    def test_off_renders_black(self, strip):
        strip.set_state(MdbLedState.Off).wait()
        strip.tick()
        _all_pixels_equal(strip.get_shown_frame(), (0.0, 0.0, 0.0))

    def test_running_renders_solid_green(self, strip):
        strip.set_state(MdbLedState.Running).wait()
        strip.tick()
        _all_pixels_equal(strip.get_shown_frame(), (0.0, 1.0, 0.0))

    def test_error_blinks_red_then_black(self, strip):
        strip.set_state(MdbLedState.Error).wait()
        strip.tick()  # step 0 → on
        _all_pixels_equal(strip.get_shown_frame(), (1.0, 0.0, 0.0))
        strip.tick()  # step 1 → off
        _all_pixels_equal(strip.get_shown_frame(), (0.0, 0.0, 0.0))

    def test_disabled_alternates_orange_per_pixel(self, strip):
        strip.set_state(MdbLedState.Disabled).wait()
        strip.tick()  # step 0
        frame = strip.get_shown_frame()
        assert frame[0][0] > 0.9 and frame[0][1] > 0.4  # orange
        assert frame[1] == (0.0, 0.0, 0.0)
        assert frame[2][0] > 0.9
        assert frame[3] == (0.0, 0.0, 0.0)

        strip.tick()  # step 1, parity flipped
        frame = strip.get_shown_frame()
        assert frame[0] == (0.0, 0.0, 0.0)
        assert frame[1][0] > 0.9 and frame[1][1] > 0.4
        assert frame[2] == (0.0, 0.0, 0.0)
        assert frame[3][0] > 0.9

    def test_loading_chases_team_color(self, strip):
        # Doubles as a check that set_team_color is actually applied.
        strip.set_team_color(0.0, 0.0, 1.0).wait()  # blue
        strip.set_state(MdbLedState.Loading).wait()
        for step in range(strip.num_pixels * 2):
            strip.tick()
            frame = strip.get_shown_frame()
            lit_idx = step % strip.num_pixels
            for i, (r, g, b) in enumerate(frame):
                if i == lit_idx:
                    assert abs(b - 1.0) < 1 / 255 + 1e-9
                else:
                    assert (r, g, b) == (0.0, 0.0, 0.0)

    def test_loading_chase_width(self, wide_strip):
        # 12-pixel strip, 5-pixel chase. Step 0 should light pixels 0..4
        # in team color and leave the other 7 black.
        wide_strip.set_team_color(0.0, 0.0, 1.0).wait()  # blue
        wide_strip.set_state(MdbLedState.Loading).wait()
        wide_strip.tick()
        frame = wide_strip.get_shown_frame()
        for i in range(5):
            assert abs(frame[i][2] - 1.0) < 1 / 255 + 1e-9, f"pixel {i} should be blue"
        for i in range(5, 12):
            assert frame[i] == (0.0, 0.0, 0.0), f"pixel {i} should be black"

        # Step 1 → window slides by one (pixels 1..5 lit).
        wide_strip.tick()
        frame = wide_strip.get_shown_frame()
        assert frame[0] == (0.0, 0.0, 0.0)
        for i in range(1, 6):
            assert abs(frame[i][2] - 1.0) < 1 / 255 + 1e-9
        for i in range(6, 12):
            assert frame[i] == (0.0, 0.0, 0.0)

    def test_state_change_resets_step(self, strip):
        # In Loading, step n picks pixel n % num_pixels. After advancing,
        # switching to a different state must restart the chase from 0.
        strip.set_state(MdbLedState.Loading).wait()
        for _ in range(3):
            strip.tick()

        strip.set_state(MdbLedState.Off).wait()
        strip.set_state(MdbLedState.Loading).wait()
        strip.tick()  # should render step 0 → only pixel 0 lit

        frame = strip.get_shown_frame()
        assert frame[0] != (0.0, 0.0, 0.0)
        for i in range(1, strip.num_pixels):
            assert frame[i] == (0.0, 0.0, 0.0)


class TestStateRoundTrip:
    """Cover get_state / get_team_color paths that rendering tests don't hit."""

    def test_state_and_team_color_round_trip(self, strip):
        strip.set_state(MdbLedState.Loading).wait()
        strip.set_team_color(0.1, 0.2, 0.3).wait()

        (state,) = strip.get_state().wait()
        assert state == MdbLedState.Loading

        r, g, b = strip.get_team_color().wait()
        tol = 1 / 255 + 1e-9
        assert abs(r - 0.1) < tol
        assert abs(g - 0.2) < tol
        assert abs(b - 0.3) < tol


class TestAnimatorThread:
    """End-to-end: the animator thread + wakeup actually drive renders."""

    def test_thread_renders_running_state(self, logger):
        s = MdbLedVirtual(name="live", logger=logger, num_pixels=3)
        s.init().wait()
        try:
            s.set_state(MdbLedState.Running).wait()
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                frame = s.get_shown_frame()
                if frame and frame[0] == (0.0, 1.0, 0.0):
                    break
                time.sleep(0.01)
            else:
                pytest.fail("animator never rendered Running state within 500 ms")
            for px in s.get_shown_frame():
                assert px == (0.0, 1.0, 0.0)
        finally:
            s.close()

    def test_close_stops_thread(self, logger):
        s = MdbLedVirtual(name="live2", logger=logger, num_pixels=3)
        s.init().wait()
        s.set_state(MdbLedState.Loading).wait()
        time.sleep(0.05)
        s.close()
        leaked = [
            t for t in threading.enumerate()
            if t.name == "mdb-led-live2" and t.is_alive()
        ]
        assert leaked == [], f"animator thread leaked: {leaked}"


class TestSwapInvariant:
    def test_signature_parity_real_vs_virtual(self):
        """Per CLAUDE.local.md: the virtual must accept exactly the same
        kwargs as the real driver, otherwise a real↔virtual config swap
        forces edits to other lines."""
        import inspect

        real_params = set(inspect.signature(MdbLed.__init__).parameters)
        virt_params = set(inspect.signature(MdbLedVirtual.__init__).parameters)
        assert real_params == virt_params, (
            f"only-real={real_params - virt_params}, "
            f"only-virt={virt_params - real_params}"
        )
