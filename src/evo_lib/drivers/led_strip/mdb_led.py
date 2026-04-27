"""Mat-de-balise LED driver: WS2812B with state-driven animations.

The legacy MDB had a Teensy + carte-mat-de-balise running FastLED in
hardware. For Hololutek 2026 there is no MDB card yet; the mast LEDs are
wired directly to a RPi GPIO pin and driven through ``rpi_ws281x``.

Compared to a plain ``WS2812B``, ``MdbLed`` exposes the legacy-style
indication semantics (``set_state``, ``set_team_color``) backed by a
background animation thread. The high level only emits state changes —
the rendering policy lives here.

State semantics, mirroring legacy ``LightningMode``:

- ``Off``      — all pixels black, no animation (default at boot).
- ``Disabled`` — alternating orange/black per pixel, flips every 250 ms.
- ``Loading``  — wide chase in the team color (configurable width via
                 ``loading_chase_length``, default 5), 50 ms / step. Used
                 during pre-match setup; ``set_team_color`` matters here.
- ``Running``  — solid green, static (refreshed only on state change).
- ``Error``    — full-strip red blink, 500 ms.

Inheritance chain: ``MdbLedVirtual → MdbLed → WS2812B``. The virtual
overrides only the four hardware hooks exposed by ``WS2812B`` (no
re-implementation of pixel arithmetic or state machine).
"""

import threading
from enum import IntEnum

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.led_strip.ws2812b import (
    _DEFAULT_DMA_CHANNEL,
    _DEFAULT_FREQUENCY_HZ,
    _DEFAULT_PIN,
    WS2812B,
    _clamp_unit,
    _unpack_rgb,
)
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class MdbLedState(IntEnum):
    """High-level states the mat-de-balise indicator displays.

    Names mirror the legacy ``LightningMode`` so muscle memory transfers.
    """

    Off = 0
    Disabled = 1
    Loading = 2
    Running = 3
    Error = 4


# Per-state refresh delay in seconds. ``None`` = static (animator parks
# until the next state/team-color change).
_REFRESH_S: dict[MdbLedState, float | None] = {
    MdbLedState.Off:      None,
    MdbLedState.Running:  None,
    MdbLedState.Disabled: 0.25,
    MdbLedState.Error:    0.50,
    MdbLedState.Loading:  0.05,
}


class MdbLed(WS2812B):
    """WS2812B + state-machine animator for the mat-de-balise indicator.

    The animator runs in a daemon thread that idles on a condition variable
    when the current state is static (``Off`` / ``Running``). State changes
    wake it up immediately — ``set_state`` returns without blocking.

    A ``set_pixel`` / ``fill`` / ``show`` call from outside while the
    animator is in a non-static state will race with it and likely be
    overwritten on the next render. Drive the indicator through state
    changes; reach for the raw ``LedStrip`` API only when in ``Off`` state.
    """

    commands = DriverCommands(parents=[WS2812B.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        num_pixels: int,
        pin: int = _DEFAULT_PIN,
        brightness: float = 1.0,
        frequency_hz: int = _DEFAULT_FREQUENCY_HZ,
        dma_channel: int = _DEFAULT_DMA_CHANNEL,
        team_color_r: float = 1.0,
        team_color_g: float = 0.8,
        team_color_b: float = 0.0,
        loading_chase_length: int = 5,
        auto_start_animator: bool = True,
    ):
        super().__init__(name, logger, num_pixels, pin, brightness, frequency_hz, dma_channel)
        self._state: MdbLedState = MdbLedState.Off
        self._team_color: tuple[float, float, float] = (
            _clamp_unit(team_color_r),
            _clamp_unit(team_color_g),
            _clamp_unit(team_color_b),
        )
        # Width of the comet head in Loading state. Clamped so it never
        # exceeds the strip length (would lit every pixel and look static).
        self._loading_chase_length: int = max(1, min(loading_chase_length, num_pixels))
        self._step: int = 0
        # Lock guards _state / _team_color / _step against animator vs
        # caller-thread races. Held only briefly — never around hardware
        # calls — so it never serializes the rpi_ws281x DMA show.
        self._state_lock = threading.Lock()
        self._stop_event = threading.Event()
        # Wakes the animator early when state or team color changes.
        self._wakeup = threading.Event()
        self._thread: threading.Thread | None = None
        self._auto_start_animator = auto_start_animator

    def init(self) -> Task[()]:
        super().init().wait()
        if self._auto_start_animator:
            self._start_animator()
        return ImmediateResultTask()

    def close(self) -> None:
        self._stop_animator()
        super().close()

    @commands.register(
        args=[("state", ArgTypes.Enum(MdbLedState, help="Indicator state"))],
        result=[],
    )
    def set_state(self, state: MdbLedState) -> Task[()]:
        with self._state_lock:
            if state == self._state:
                return ImmediateResultTask()
            self._state = state
            self._step = 0  # restart any chase / blink phase cleanly
        self._wakeup.set()
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[("state", ArgTypes.Enum(MdbLedState, help="Current indicator state"))],
    )
    def get_state(self) -> Task[MdbLedState]:
        with self._state_lock:
            return ImmediateResultTask(self._state)

    @commands.register(
        args=[
            ("r", ArgTypes.F32(help="Red 0.0-1.0")),
            ("g", ArgTypes.F32(help="Green 0.0-1.0")),
            ("b", ArgTypes.F32(help="Blue 0.0-1.0")),
        ],
        result=[],
    )
    def set_team_color(self, r: float, g: float, b: float) -> Task[()]:
        with self._state_lock:
            self._team_color = (_clamp_unit(r), _clamp_unit(g), _clamp_unit(b))
        # Wake the animator so the new color shows up immediately on the
        # next chase frame — otherwise it'd lag by up to one refresh tick.
        self._wakeup.set()
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[
            ("r", ArgTypes.F32(help="Red 0.0-1.0")),
            ("g", ArgTypes.F32(help="Green 0.0-1.0")),
            ("b", ArgTypes.F32(help="Blue 0.0-1.0")),
        ],
    )
    def get_team_color(self) -> Task[float, float, float]:
        with self._state_lock:
            r, g, b = self._team_color
        return ImmediateResultTask(r, g, b)

    # --- Animator lifecycle ------------------------------------------------

    def _start_animator(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._wakeup.set()  # render the initial frame immediately
        self._thread = threading.Thread(
            target=self._animator_loop,
            daemon=True,
            name=f"mdb-led-{self.name}",
        )
        self._thread.start()

    def _stop_animator(self) -> None:
        self._stop_event.set()
        self._wakeup.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _animator_loop(self) -> None:
        while not self._stop_event.is_set():
            self._wakeup.clear()
            with self._state_lock:
                state = self._state
                team_color = self._team_color
                step = self._step
                self._step += 1

            try:
                self._render_frame(state, team_color, step)
            except Exception as exc:
                self._log.error(f"MdbLed '{self.name}' render error: {exc}")

            delay = _REFRESH_S.get(state)
            if delay is None:
                # Static state — park until something changes.
                self._wakeup.wait()
            else:
                self._wakeup.wait(delay)

    # --- Rendering policy --------------------------------------------------
    # Pulled out as a regular method so tests can drive it deterministically
    # (see ``MdbLedVirtual.tick``).

    def _render_frame(
        self,
        state: MdbLedState,
        team_color: tuple[float, float, float],
        step: int,
    ) -> None:
        if state == MdbLedState.Off:
            self.fill(0.0, 0.0, 0.0).wait()
        elif state == MdbLedState.Running:
            # Solid green, the legacy "match in progress" indication.
            self.fill(0.0, 1.0, 0.0).wait()
        elif state == MdbLedState.Error:
            on = (step % 2) == 0
            if on:
                self.fill(1.0, 0.0, 0.0).wait()
            else:
                self.fill(0.0, 0.0, 0.0).wait()
        elif state == MdbLedState.Disabled:
            # Alternating orange/black per-pixel, parity flips every step
            # — same visual as the legacy "Disabled" mode.
            on_color = (1.0, 0.5, 0.0)
            off_color = (0.0, 0.0, 0.0)
            for i in range(self._num_pixels):
                lit = ((step + i) % 2) == 0
                r, g, b = on_color if lit else off_color
                self.set_pixel(i, r, g, b).wait()
        elif state == MdbLedState.Loading:
            # Wide chase in team color: a comet of `loading_chase_length`
            # consecutive lit pixels advances by one slot per step, with
            # wrap-around at the strip end.
            self.fill(0.0, 0.0, 0.0).wait()
            tcr, tcg, tcb = team_color
            for offset in range(self._loading_chase_length):
                idx = (step + offset) % self._num_pixels
                self.set_pixel(idx, tcr, tcg, tcb).wait()
        self.show().wait()


class MdbLedDefinition(DriverDefinition):
    """Factory for ``MdbLed`` from JSON5 config.

    Inherits the WS2812B argument set (num_pixels, pin, brightness,
    frequency_hz, dma_channel) and adds team-color defaults.
    """

    def __init__(self, logger: Logger):
        super().__init__(MdbLed.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("num_pixels", ArgTypes.U16(help="Number of LEDs in the strip"))
        defn.add_optional("pin", ArgTypes.U8(help="GPIO pin (BCM)"), _DEFAULT_PIN)
        defn.add_optional("brightness", ArgTypes.F32(help="Initial brightness 0.0-1.0"), 1.0)
        defn.add_optional(
            "frequency_hz",
            ArgTypes.U32(help="Bit clock; 800 kHz for WS2812B"),
            _DEFAULT_FREQUENCY_HZ,
        )
        defn.add_optional(
            "dma_channel",
            ArgTypes.U8(help="DMA channel"),
            _DEFAULT_DMA_CHANNEL,
        )
        defn.add_optional("team_color_r", ArgTypes.F32(help="Default team red"), 1.0)
        defn.add_optional("team_color_g", ArgTypes.F32(help="Default team green"), 0.8)
        defn.add_optional("team_color_b", ArgTypes.F32(help="Default team blue"), 0.0)
        defn.add_optional(
            "loading_chase_length",
            ArgTypes.U8(help="Comet width in Loading state (number of lit pixels)"),
            5,
        )
        return defn

    def create(self, args: DriverInitArgs) -> MdbLed:
        name = args.get_name()
        return MdbLed(
            name=name,
            logger=self._logger.get_sublogger(name),
            num_pixels=args.get("num_pixels"),
            pin=args.get("pin"),
            brightness=args.get("brightness"),
            frequency_hz=args.get("frequency_hz"),
            dma_channel=args.get("dma_channel"),
            team_color_r=args.get("team_color_r"),
            team_color_g=args.get("team_color_g"),
            team_color_b=args.get("team_color_b"),
            loading_chase_length=args.get("loading_chase_length"),
        )


class MdbLedVirtual(MdbLed):
    """Drop-in twin of ``MdbLed`` with an in-memory pixel buffer.

    Inherits ``MdbLed`` for the state machine + animator (no duplication)
    and overrides ``WS2812B``'s four hardware hooks to back the strip with
    a buffer instead of rpi_ws281x. Constructor signature is identical to
    ``MdbLed`` (same swap invariant as ``WS2812BVirtual``).
    """

    commands = DriverCommands(parents=[MdbLed.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        num_pixels: int,
        pin: int = _DEFAULT_PIN,
        brightness: float = 1.0,
        frequency_hz: int = _DEFAULT_FREQUENCY_HZ,
        dma_channel: int = _DEFAULT_DMA_CHANNEL,
        team_color_r: float = 1.0,
        team_color_g: float = 0.8,
        team_color_b: float = 0.0,
        loading_chase_length: int = 5,
        auto_start_animator: bool = True,
    ):
        super().__init__(
            name=name,
            logger=logger,
            num_pixels=num_pixels,
            pin=pin,
            brightness=brightness,
            frequency_hz=frequency_hz,
            dma_channel=dma_channel,
            team_color_r=team_color_r,
            team_color_g=team_color_g,
            team_color_b=team_color_b,
            loading_chase_length=loading_chase_length,
            auto_start_animator=auto_start_animator,
        )
        self._buffer: list[int] = [0] * num_pixels
        self._shown: list[int] = [0] * num_pixels
        self._brightness_byte: int = round(self._brightness * 255)

    # --- Hardware hooks (override WS2812B) --------------------------------

    def _hw_init_strip(self) -> None:
        pass

    def _hw_close_strip(self) -> None:
        pass

    def _hw_set_pixel(self, index: int, packed: int) -> None:
        self._buffer[index] = packed

    def _hw_get_pixel(self, index: int) -> int:
        return self._buffer[index]

    def _hw_show(self) -> None:
        self._shown = list(self._buffer)

    def _hw_set_brightness(self, byte_value: int) -> None:
        self._brightness_byte = byte_value

    # --- Test helpers -----------------------------------------------------

    def get_shown_frame(self) -> list[tuple[float, float, float]]:
        """RGB triplets actually pushed via ``show`` (animator output)."""
        return [_unpack_rgb(p) for p in self._shown]

    def tick(self) -> None:
        """Render one animation frame deterministically.

        For tests that want to assert on each step without racing with the
        background thread. Construct with ``auto_start_animator=False`` to
        keep the thread offline; then call ``tick`` after each
        ``set_state`` / ``set_team_color``.
        """
        with self._state_lock:
            state = self._state
            team_color = self._team_color
            step = self._step
            self._step += 1
        self._render_frame(state, team_color, step)


class MdbLedVirtualDefinition(DriverDefinition):
    """Factory for ``MdbLedVirtual``. Mirrors ``MdbLedDefinition`` so the
    config can swap real↔virtual by changing only the driver name."""

    def __init__(self, logger: Logger):
        super().__init__(MdbLedVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("num_pixels", ArgTypes.U16(help="Number of LEDs in the strip"))
        defn.add_optional("pin", ArgTypes.U8(help="GPIO pin (BCM, ignored)"), _DEFAULT_PIN)
        defn.add_optional("brightness", ArgTypes.F32(help="Initial brightness 0.0-1.0"), 1.0)
        defn.add_optional(
            "frequency_hz",
            ArgTypes.U32(help="Bit clock (ignored)"),
            _DEFAULT_FREQUENCY_HZ,
        )
        defn.add_optional(
            "dma_channel",
            ArgTypes.U8(help="DMA channel (ignored)"),
            _DEFAULT_DMA_CHANNEL,
        )
        defn.add_optional("team_color_r", ArgTypes.F32(help="Default team red"), 1.0)
        defn.add_optional("team_color_g", ArgTypes.F32(help="Default team green"), 0.8)
        defn.add_optional("team_color_b", ArgTypes.F32(help="Default team blue"), 0.0)
        defn.add_optional(
            "loading_chase_length",
            ArgTypes.U8(help="Comet width in Loading state (number of lit pixels)"),
            5,
        )
        return defn

    def create(self, args: DriverInitArgs) -> MdbLedVirtual:
        name = args.get_name()
        return MdbLedVirtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            num_pixels=args.get("num_pixels"),
            pin=args.get("pin"),
            brightness=args.get("brightness"),
            frequency_hz=args.get("frequency_hz"),
            dma_channel=args.get("dma_channel"),
            team_color_r=args.get("team_color_r"),
            team_color_g=args.get("team_color_g"),
            team_color_b=args.get("team_color_b"),
            loading_chase_length=args.get("loading_chase_length"),
        )
