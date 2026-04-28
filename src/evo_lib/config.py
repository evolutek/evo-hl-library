from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

import json5
import pydantic

if TYPE_CHECKING:
    from evo_lib.argtypes import ArgType, ArgTypes

type ConfigValue = None | bool | str | int | float | list[ConfigValue] | ConfigObject


class ConfigValidationError(ValueError):
    pass


class ConfigObject(dict[str, ConfigValue]):
    def __init__(
        self,
        parent_key: str | None = None,
        parent_object: ConfigObject | None = None,
        map: dict[str, ConfigValue] | None = None,
    ):
        super().__init__(map or {})
        self._parent_object = parent_object
        self._parent_key = parent_key

    def create_object(self, key: str) -> ConfigObject:
        r = ConfigObject(key, self)
        self[key] = r
        return r

    def create_list(self, key: str) -> list:
        r = []
        self[key] = r
        return r

    def _get_key_path(self, key: str) -> str:
        path = [key]
        node = self
        while node._parent_object is not None:
            path.append(node._parent_key or "")
            node = node._parent_object
        return ".".join(reversed(path))

    def _get_required(
        self, key: str, value_types: list[type], value_type_name: str, argtype: ArgType | None
    ) -> Any:
        if key not in self:
            raise ConfigValidationError(
                f"Expecting a value at '{self._get_key_path(key)}' but nothing found"
            )
        value = self[key]
        if type(value) not in value_types:
            raise ConfigValidationError(
                f"Expecting value at '{self._get_key_path(key)}' to be {value_type_name}"
            )
        if argtype is not None:
            return argtype.value_from_config(value)
        return value

    def get_bool(self, key: str, argtype: "ArgTypes.Bool | None" = None) -> bool:
        return self._get_required(key, [bool], "a boolean", argtype)

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

    def _get_optional(
        self, key: str, default: Any, argtype: ArgType | None, getter: Callable
    ) -> Any:
        if key in self:
            return getter(key, argtype)
        else:
            return default

    def get_float_or(
        self, key: str, default: float, argtype: ArgTypes.Float | None = None
    ) -> float:
        return self._get_optional(key, default, argtype, self.get_float)

    def get_int_or(self, key: str, default: int, argtype: ArgTypes.Float | None = None) -> int:
        return self._get_optional(key, default, argtype, self.get_int)

    def get_bool_or(self, key: str, default: bool, argtype: ArgTypes.Float | None = None) -> bool:
        return self._get_optional(key, default, argtype, self.get_bool)

    def get_str_or(self, key: str, default: str, argtype: ArgTypes.Float | None = None) -> str:
        return self._get_optional(key, default, argtype, self.get_str)

    def get_array_or(self, key: str, default: list, argtype: ArgTypes.Float | None = None) -> list:
        return self._get_optional(key, default, argtype, self.get_array)

    def get_object_or(
        self, key: str, default: ConfigObject, argtype: ArgTypes.Float | None = None
    ) -> ConfigObject:
        return self._get_optional(key, default, argtype, self.get_object)


class ConfigParser(ABC):
    @abstractmethod
    def parse_from_file(self, file_path: str) -> ConfigValue:
        pass

    @abstractmethod
    def parse_from_string(self, string: str) -> ConfigValue:
        pass


class ConfigFormatter(ABC):
    @abstractmethod
    def format_to_file(self, config: ConfigValue, file_path: str) -> None:
        pass

    @abstractmethod
    def format_to_string(self, config: ConfigValue) -> str:
        pass


class ConfigJSON5Parser(ConfigParser):
    def _transform_raw_config(
        self,
        raw: ConfigValue | dict | list,
        key: str | None = None,
        parent: ConfigObject | None = None,
    ) -> ConfigValue:
        if isinstance(raw, dict):
            v = ConfigObject(key, parent, raw)
            for key, value in v.items():
                v[key] = self._transform_raw_config(value, key, v)
            return v
        elif isinstance(raw, list):
            for i in range(len(raw)):
                raw[i] = self._transform_raw_config(raw[i], str(i), parent)
        return raw

    def parse_from_file(self, filepath: str) -> ConfigValue:
        with open(filepath, "r", encoding="utf8") as f:
            raw_config = json5.load(f)
        return self._transform_raw_config(raw_config)

    def parse_from_string(self, string: str) -> ConfigValue:
        return self._transform_raw_config(json5.loads(string))


class ConfigJSON5Formatter(ConfigFormatter):
    def __init__(self, indent: int = 4):
        super().__init__()
        self._indent = indent

    def format_to_file(self, config: ConfigValue, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            json5.dump(config, f, indent = self._indent, quote_keys = True)
            f.write("\n")

    def format_to_string(self, config: ConfigValue) -> str:
        return json5.dumps(config, indent = self._indent, quote_keys = True)


class ConfigSchema(ABC):
    @abstractmethod
    def validate(self, config: ConfigValue) -> Any:
        pass


class ConfigPydanticSchema(ConfigSchema):
    def __init__(self, model: type[pydantic.BaseModel]):
        super().__init__()
        self.model = model

    def validate(self, config: ConfigValue) -> Any:
        if not isinstance(config, dict):
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
