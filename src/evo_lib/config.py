from abc import ABC, abstractmethod
from typing import Any, Callable

import json5
import pydantic

from evo_lib.argtypes import ArgType, ArgTypes

type ConfigValue = None | bool | str | int | float | list[ConfigValue] | ConfigObject


class ConfigValidationError(ValueError):
    pass


class ConfigObject(dict[str, ConfigValue]):
    def __init__(
        self,
        parent_key: str | None,
        parent_object: ConfigObject | None,
        map: dict[str, ConfigValue] = dict()
    ):
        super().__init__(map)
        self._parent_object = parent_object
        self._parent_key = parent_key

    def _get_key_path(self, key: str) -> str:
        path = [key]
        node = self
        while node._parent_object is not None:
            path.append(node._parent_key or "")
            node = node._parent_object
        return ".".join(path.reverse())

    def _get_required(self, key: str, value_types: list[type], value_type_name: str, argtype: ArgType | None) -> Any:
        if key not in self:
            raise ConfigValidationError(f"Expecting a value at '{self._get_key_path(key)}' but nothing found")
        value = self[key]
        if type(value) not in value_types:
            raise ConfigValidationError(f"Expecting value at '{self._get_key_path(key)}' to be {value_type_name}")
        if argtype is not None:
            return argtype.value_from_config(value)
        return value

    def get_bool(self, key: str) -> bool:
        return self._get_required(key, [bool], "a boolean", None)

    def get_str(self, key: str, argtype: ArgTypes.String | None = None) -> str:
        return self._get_required(key, [str], "a string", argtype)

    def get_int(self, key: str, argtype: ArgTypes.Int | None = None) -> int:
        return self._get_required(key, [int], "an integer", argtype)

    def get_float(self, key: str, argtype: ArgTypes.Float | None = None) -> float:
        return self._get_required(key, [int, float], "a number", argtype)

    def get_array(self, key: str, argtype: ArgTypes.Array | None = None) -> list[ConfigValue]:
        return self._get_required(key, [list], "an array/list", argtype)

    def get_object(self, key: str, argtype: ArgTypes.Struct | None = None) -> ConfigObject:
        return self._get_required(key, [ConfigObject], "an object/dictionary", argtype)

    def _get_optional(self, key: str, default: Any, argtype: ArgType, getter: Callable) -> Any:
        if key in self:
            return getter(key, argtype)
        else:
            return default

    def get_float_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> float:
        return self._get_optional(key, default, argtype, self.get_float)

    def get_int_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> int:
        return self._get_optional(key, default, argtype, self.get_int)

    def get_bool_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> bool:
        return self._get_optional(key, default, argtype, self.get_bool)

    def get_str_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> str:
        return self._get_optional(key, default, argtype, self.get_str)

    def get_array_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> list:
        return self._get_optional(key, default, argtype, self.get_array)

    def get_object_or(self, key: str, default: float, argtype: ArgTypes.Float | None = None) -> ConfigObject:
        return self._get_optional(key, default, argtype, self.get_object)


class ConfigParser(ABC):
    @abstractmethod
    def parse_file(self, filepath: str) -> ConfigValue:
        pass

    @abstractmethod
    def parse_string(self, string: str) -> ConfigValue:
        pass


class ConfigJSON5Parser(ConfigParser):
    def _transform_raw_config(
        self,
        raw: ConfigValue | dict | list,
        key: str | None = None,
        parent: ConfigObject | None = None
    ) -> ConfigValue:
        if isinstance(raw, dict):
            v = ConfigObject(parent, key, raw)
            for key, value in v.items():
                v[key] = self._transform_raw_config(value, key, v)
            return v
        return raw

    def parse_file(self, filepath: str) -> ConfigValue:
        with open(filepath, "r", encoding="utf8") as f:
            raw_config = json5.load(f)
        return self._transform_raw_config(raw_config)

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


class ConfigArgTypeSchema(ConfigSchema):
    def __init__(self, model: ArgType):
        super().__init__()
        self.model = model

    def validate(self, config: ConfigValue) -> Any:
        return self.model.value_from_config(config)
