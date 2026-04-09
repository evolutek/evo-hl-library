from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgType

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
        self.args: dict[str,] = dict()
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


class DriverDefinition(ABC):
    @abstractmethod
    def create(self, args: DriverInitArgs) -> Peripheral:
        pass

    @abstractmethod
    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        pass
