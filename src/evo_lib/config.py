from abc import ABC, abstractmethod
from typing import Any

import json5
import pydantic

type ConfigValue = None | bool | str | int | float | list[ConfigValue] | dict[str,ConfigValue]


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
