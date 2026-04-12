"""PWM drivers: virtual implementations for testing and simulation."""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands, DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.pwm import PWM
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 16


class PWMVirtual(PWM):
    """In-memory PWM channel for tests and simulation.

    Exposes read-back commands (get_duty_cycle, get_pulse_width_us, is_enabled)
    on top of the real PWM commands so the REPL can observe simulated state.
    """

    commands = DriverCommands(parents=[PWM.commands])

    def __init__(self, name: str, logger: Logger, freq_hz: float = 50.0):
        super().__init__(name)
        self._log = logger
        self._freq_hz = freq_hz
        self.duty_cycle: float = 0.0
        self.pulse_width_us: float = 0.0
        self.enabled: bool = False

    def init(self) -> Task[()]:
        self.enabled = True
        self._log.info(f"PWMVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self.enabled = False

    def set_duty_cycle(self, duty: float) -> Task[()]:
        self.duty_cycle = max(0.0, min(1.0, duty))
        self.pulse_width_us = self.duty_cycle * 1_000_000.0 / self._freq_hz
        return ImmediateResultTask(None)

    def set_pulse_width_us(self, width_us: float) -> Task[()]:
        period_us = 1_000_000.0 / self._freq_hz
        self.duty_cycle = max(0.0, min(1.0, width_us / period_us))
        self.pulse_width_us = self.duty_cycle * period_us
        return ImmediateResultTask(None)

    def free(self) -> Task[()]:
        self.duty_cycle = 0.0
        self.pulse_width_us = 0.0
        return ImmediateResultTask(None)

    @commands.register(
        args=[],
        result=[("duty", ArgTypes.F32(help="Current duty cycle (0.0 to 1.0)"))],
    )
    def get_duty_cycle(self) -> Task[float]:
        """Read the last commanded duty cycle."""
        return ImmediateResultTask(self.duty_cycle)

    @commands.register(
        args=[],
        result=[("width_us", ArgTypes.F32(help="Current pulse width in microseconds"))],
    )
    def get_pulse_width_us(self) -> Task[float]:
        """Read the last commanded pulse width."""
        return ImmediateResultTask(self.pulse_width_us)

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="True if init() has been called and close() has not"))],
    )
    def is_enabled(self) -> Task[bool]:
        """Read whether the simulated channel is enabled."""
        return ImmediateResultTask(self.enabled)


class PWMChipVirtual(InterfaceHolder):
    """In-memory virtual for the PCA9685 chip, for tests and simulation."""

    def __init__(self, name: str, logger: Logger, freq_hz: float = 50.0):
        super().__init__(name)
        self._log = logger
        self._freq_hz = freq_hz
        self._channels: dict[int, PWMVirtual] = {}

    def init(self) -> Task[()]:
        self._log.info(f"PWMChipVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self._channels.clear()

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._channels.values())

    def get_channel(self, channel: int, name: str) -> PWMVirtual:
        """Create or retrieve a PWMVirtual for the given channel number."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel in self._channels:
            return self._channels[channel]
        pwm = PWMVirtual(name, self._log, self._freq_hz)
        self._channels[channel] = pwm
        return pwm


class PWMChipVirtualDefinition(DriverDefinition):
    """Factory for PWMChipVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("freq_hz", ArgTypes.F32(), 50.0)
        return defn

    def create(self, args: DriverInitArgs) -> PWMChipVirtual:
        return PWMChipVirtual(
            name=args.get_name(),
            logger=self._logger,
            freq_hz=args.get("freq_hz"),
        )
