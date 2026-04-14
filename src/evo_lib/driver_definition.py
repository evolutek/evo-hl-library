from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from evo_lib.argtypes import ArgType
from evo_lib.registry import Registry
from evo_lib.task import Task

if TYPE_CHECKING:
    from evo_lib.peripheral import Peripheral


# Description of one initialization argument
class DriverInitArgDefinition:
    def __init__(self, type: ArgType, required: bool, default: Any = None) -> None:
        self.type = type
        self.required = required
        self.default = default

    def is_required(self) -> bool:
        return self.required

    def get_type(self) -> ArgType:
        return self.type

    def get_default(self) -> Any:
        return self.default


# Description of the initialization arguments of a driver
class DriverInitArgsDefinition:
    def __init__(self, **kwargs) -> None:
        self.args: dict[str, DriverInitArgDefinition] = {}

    def get_args(self) -> dict[str, DriverInitArgDefinition]:
        return self.args

    def add_required(self, key: str, arg_type: ArgType) -> None:
        self.args[key] = DriverInitArgDefinition(arg_type, True)

    def add_optional(self, key: str, arg_type: ArgType, default) -> None:
        self.args[key] = DriverInitArgDefinition(arg_type, False, default)


# Initilization arguments values of a driver instance
class DriverInitArgs:
    def __init__(self, name: str, definition: DriverInitArgsDefinition) -> None:
        self.definition = definition
        self.args: dict[str, Any] = dict()
        self._name: str = name

    def get_name(self) -> str:
        return self._name

    def set(self, key: str, value: Any) -> None:
        self.args[key] = value

    def get(self, key: str):
        if key in self.args:
            return self.args[key]
        return self.definition.args[key].default

    def get_all(self) -> list[tuple[str, Any, ArgType]]:
        r: list[tuple[str, Any, ArgType]] = []
        for name, arg_def in self.definition.get_args().items():
            r.append((name, self.get(name), arg_def.get_type()))
        return r


type DriverCommandCallback = Callable[..., Task[Any]]


# A driver command is an unbound method: it takes the peripheral instance as
# first positional argument, plus any keyword arguments, and returns a Task.
@dataclass
class DriverCommand:
    name: str
    method: str
    args: list[tuple[str, ArgType]]
    result: list[tuple[str, ArgType]]
    help: str | None

    def call(self, obj: Peripheral, *args, **kwargs) -> Task[Any]:
        return getattr(obj, self.method)(*args, **kwargs)


class DriverCommands:
    def __init__(self, parents: list[DriverCommands] | None = None):
        self._commands: Registry[DriverCommand] = Registry("driver_commands")
        for parent in (parents or []):
            for cmd in parent._commands.get_all():
                if not self._commands.has(cmd.name):
                    self._commands.register(cmd.name, cmd)

    def register(self,
        args: list[tuple[str, ArgType]],
        result: list[tuple[str, ArgType]],
        name: str | None = None,
        help: str | None = None
    ) -> DriverCommand:
        def decorator(callback: DriverCommandCallback):
            # Create a wrapper to call the method of the instance class not the method on
            # which this decorator was called, because this decorator can be used on
            # interface's method, but interface method do not have any implementation.
            command = DriverCommand(
                name = callback.__name__ if name is None else name,
                method = callback.__name__,
                args = args,
                result = result,
                help = help
            )
            self._commands.register(command.name, command)

            return callback
        return decorator

    def get(self, name: str) -> DriverCommand:
        return self._commands.get(name)

    def get_all(self) -> list[DriverCommand]:
        return self._commands.get_all()


class DriverDefinition(ABC):
    def __init__(self, commands: DriverCommands | None = None) -> None:
        # Commands are unbound methods exposed by the driver class, callable as
        # ``command(peripheral_instance, **kwargs) -> Task``. Subclasses register
        # them via ``register_command`` (typically in their own ``__init__``).
        self._commands = commands if commands is not None else DriverCommands()
        self._name: str | None = None

    def set_name(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name

    def get_commands(self) -> DriverCommands:
        """Return a copy of all registered commands."""
        return self._commands

    @abstractmethod
    def create(self, args: DriverInitArgs) -> Peripheral:
        """Instantiate the peripheral from config-provided arguments.

        Callers (typically the ComponentsManager) are responsible for linking
        the returned peripheral back to its definition by setting
        ``peripheral._definition = self`` after ``create`` returns, so that
        ``peripheral.get_definition()`` is usable at runtime.
        """

    @abstractmethod
    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        pass
