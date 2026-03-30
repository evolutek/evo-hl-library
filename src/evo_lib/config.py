from abc import ABC, abstractmethod
from typing import Any

import json5
import pydantic

from evo_lib.argtypes import ArgTypes

type ConfigValue = None | bool | str | int | float | list[ConfigValue] | ConfigObject


class ConfigObject(dict[str, ConfigValue]):
    def __init__(self, parent: ConfigObject | None):
        self._parent = parent

    def get_str(self, key: str, default: str | None = None, argtype: ArgTypes.String | None = None) -> str:
        pass # TODO

    def get_int(self, key: str, default: int | None = None, argtype: ArgTypes.I64 | None = None) -> int:
        pass # TODO

    def get_float(self, key: str, default: float | None = None, argtype: ArgTypes.F64 | None = None) -> float:
        pass # TODO

    def get_bool(self, key: str, default: bool | None = None) -> bool:
        pass # TODO

    def get_array(self, key: str, default: list | None = None, argtype: ArgTypes.Array | None = None) -> list[ConfigValue]:
        pass # TODO

    def get_object(self, key: str, default: ConfigObject | None = None, argtype: ArgTypes.Struct | None = None) -> ConfigObject:
        pass # TODO


class ConfigValidationError(ValueError):
    pass


class ConfigParser(ABC):
    @abstractmethod
    def parse_file(self, filepath: str) -> ConfigValue:
        pass

    @abstractmethod
    def parse_string(self, string: str) -> ConfigValue:
        pass


class ConfigJSON5Parser(ConfigParser):
    def parse_file(self, filepath: str) -> ConfigValue:
        with open(filepath, "r", encoding="utf8") as f:
            return json5.load(f)

    def parse_string(self, string: str) -> ConfigValue:
        return json5.loads(string)


class ConfigSchema(ABC):
    @abstractmethod
    def validate(self, raw: ConfigValue) -> Any:
        pass


class ConfigPydanticSchema(ConfigSchema):
    def __init__(self, model: type[pydantic.BaseModel]):
        super().__init__()
        self.model = model

    def validate(self, config: ConfigValue) -> Any:
        if type(config) is not dict:
            raise ConfigValidationError("Root config value should be a dictionary")

        try:
            result = self.model(**config)
        except pydantic.ValidationError as e:
            raise ConfigValidationError(str(e)) from e

        return result
