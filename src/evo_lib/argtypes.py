import io
import math
import re
import struct
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING, Any

from evo_lib.config import ConfigJSON5Parser, ConfigObject, ConfigValidationError, ConfigValue

if TYPE_CHECKING:
    from evo_lib.peripheral import Peripheral
    from evo_lib.registry import Registry


class ArgType(ABC):
    def __init__(self, help: str | None = None):
        self.help = help

    def value_from_str(self, v: str) -> Any:
        """Parse a string to the given argument type (usefull for CLI)."""
        return self.value_from_config(ConfigJSON5Parser().parse_from_string(v)) # Default implementation

    @abstractmethod
    def value_from_config(self, v: ConfigValue) -> Any:
        """Check if a configuration value follow type's constraints and return
        the value in the correct type (usefull for config validation)."""
        pass

    @abstractmethod
    def value_from_stream(self, s: io.RawIOBase) -> Any:
        """Decode the value from a stream (usefull for communication protocol)."""
        pass

    @abstractmethod
    def value_to_stream(self, v: Any, s: io.RawIOBase) -> None:
        """Encode a value into a stream (usefull for communication protocol)."""
        pass

    @abstractmethod
    def self_to_stream(self, s: io.RawIOBase) -> None:
        """Serialize self type settings into a stream (usefull to send command
        format over a communication protocol)."""
        pass

    @abstractmethod
    def self_from_stream(self, s: io.RawIOBase) -> None:
        """Deserialize self type from a stream (usefull to recv command format
        over a communication protocol)."""
        pass

    @abstractmethod
    def self_from_config(self, c: ConfigObject) -> None:
        """Parse self type from a config."""
        pass

    @abstractmethod
    def self_to_config(self, c: ConfigObject) -> None:
        """Dump sel type into a config."""
        pass


class ArgTypes:
    class Struct(ArgType):
        def __init__(self, fields: list[tuple[str, ArgType]]):
            self.fields: list[tuple[str, ArgType]] = fields

        def value_from_config(self, v: ConfigValue) -> dict:
            r = {}
            if isinstance(v, dict):
                for fname, ftype in self.fields:
                    r[fname] = ftype.value_from_config(v[fname])
            else:
                raise ConfigValidationError("Struct value must be a dict")
            return r

        def value_from_stream(self, s: io.RawIOBase) -> dict[str,]:
            r = {}
            for fname, ftype in self.fields:
                r[fname] = ftype.value_from_stream(s)
            return r

        def value_to_stream(self, v: dict | object, s: io.RawIOBase) -> None:
            if isinstance(v, dict):
                for fname, ftype in self.fields:
                    ftype.value_to_stream(v[fname], s)
            else:
                for fname, ftype in self.fields:
                    ftype.value_to_stream(getattr(v, fname), s)

        def self_to_stream(self, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", len(self.fields)))
            for fname, ftype in self.fields:
                fname_bytes = fname.encode("utf-8")
                s.write(struct.pack("I", len(fname_bytes)))
                s.write(fname_bytes)
                argtype_to_stream(ftype, s)

        def self_from_stream(self, s: io.RawIOBase) -> None:
            nb_fields = struct.unpack("I", s.read(4))[0]
            self.fields = []
            self.fields.clear()
            for _ in range(nb_fields):
                fname_len = struct.unpack("I", s.read(4))[0]
                fname = s.read(fname_len).decode("utf-8")
                ftype = argtype_from_stream(s)
                self.fields.append((fname, ftype))

        def self_from_config(self, c: ConfigObject) -> None:
            fields = c.get_array("fields")
            self.fields.clear()
            for field in fields:
                fname = field.get_str("name")
                ftype = argtype_from_config(field.get_str("type"))
                self.fields.append((fname, ftype))

        def value_from_str(self, v) -> object:
            r = {}
            if isinstance(v, dict):
                for fname, ftype in self.fields:
                    r[fname] = ftype.value_from_str(v[fname])
            else:
                for fname, ftype in self.fields:
                    r[fname] = ftype.value_from_str(getattr(v, fname))
            return r

    class Array(ArgType):
        def __init__(self, element_type: ArgType, max_size: int = 0):
            self.max_size = max_size
            self.element_type = element_type

        def value_from_config(self, v: ConfigValue) -> list:
            if not isinstance(v, list):
                raise ConfigValidationError("Array value must be a list")
            return [self.element_type.value_from_config(item) for item in v]

        def value_from_stream(self, s: io.RawIOBase) -> list:
            length = struct.unpack("I", s.read(4))[0]
            result = []
            for _ in range(length):
                result.append(self.element_type.value_from_stream(s))
            return result

        def value_to_stream(self, v: list, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", len(v)))
            for e in v:
                self.element_type.value_to_stream(e, s)

        def self_to_stream(self, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", self.max_size))
            argtype_to_stream(self.element_type, s)

        def self_from_stream(self, s: io.RawIOBase) -> None:
            self.max_size = struct.unpack("I", s.read(4))[0]
            self.element_type = argtype_from_stream(s)

        def self_from_config(self, c: ConfigObject) -> None:
            if "max_size" in c:
                self.max_size = c.get_int("max_size")
            if "element_type" in c:
                self.element_type = argtype_from_config(c.get_object("element_type"))

        def self_to_config(self, c: ConfigObject) -> None:
            if self.max_size != 0:
                c["max_size"] = self.max_size
            c["element_type"] = argtype_to_config(self.element_type)

    class Bytes(ArgType):
        def __init__(self, max_size: int = 0):
            self.max_size = max_size

        def value_from_config(self, v: ConfigValue) -> bytes:
            if isinstance(v, str):
                return v.encode("utf-8")
            elif isinstance(v, bytes):
                return v
            else:
                raise ConfigValidationError("Bytes value must be a string or bytes")

        def value_from_stream(self, s: io.RawIOBase) -> bytes:
            size = struct.unpack("I", s.read(4))[0]
            return s.read(size)

        def value_to_stream(self, v: bytes, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", len(v)))
            s.write(v)

        def self_to_stream(self, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", self.max_size))

        def self_from_stream(self, s: io.RawIOBase) -> None:
            self.max_size = struct.unpack("I", s.read(4))[0]

        def self_from_config(self, c: ConfigObject) -> None:
            if "max_size" in c:
                self.max_size = c.get_int("max_size")

        def self_to_config(self, c: ConfigObject) -> None:
            if self.max_size != 0:
                c["max_size"] = self.max_size

    class String(ArgType):
        def __init__(
            self,
            encoding: str = "utf-8",
            max_size: int = 0,
            choices: list[str] | None = None,
            regex: str | re.Pattern | None = None
        ):
            self.encoding = encoding
            self.choices = choices
            self.max_size = max_size
            if isinstance(regex, str):
                self.regex = re.compile(regex)
            else:
                self.regex = regex

        def value_from_config(self, v: ConfigValue) -> str:
            if not isinstance(v, str):
                raise ConfigValidationError("String value must be a string")
            if self.choices and v not in self.choices:
                raise ConfigValidationError(f"String value must be one of: {self.choices}")
            if self.regex is not None and self.regex.fullmatch(v) is None:
                raise ConfigValidationError(f"String must follow regex: {self.regex}")
            return v

        def value_from_str(self, v: str) -> str:
            return str(v)

        def value_from_stream(self, s: io.RawIOBase) -> str:
            size = struct.unpack("I", s.read(4))[0]
            return s.read(size).decode(self.encoding)

        def value_to_stream(self, v: str, s: io.RawIOBase) -> None:
            b = v.encode(self.encoding)
            s.write(struct.pack("I", len(b)))
            s.write(b)

        def self_to_stream(self, s: io.RawIOBase) -> None:
            encoding_bytes = self.encoding.encode("utf-8")
            # Write encoding
            s.write(struct.pack("I", len(encoding_bytes)))
            s.write(encoding_bytes)
            # Write max size
            s.write(struct.pack("I", self.max_size))
            # Write regex
            if self.regex:
                regex_bytes = self.regex.pattern.encode("utf-8")
                s.write(struct.pack("I", len(regex_bytes)))
                s.write(regex_bytes)
            else:
                s.write(struct.pack("I", 0))
            # Write choices
            if self.choices:
                s.write(struct.pack("I", len(self.choices)))
                for choice in self.choices:
                    choice_bytes = choice.encode("utf-8")
                    s.write(struct.pack("I", len(choice_bytes)))
                    s.write(choice_bytes)
            else:
                s.write(struct.pack("I", 0))

        def self_from_stream(self, s: io.RawIOBase) -> None:
            encoding_len = struct.unpack("I", s.read(4))[0]
            self.encoding = s.read(encoding_len).decode("utf-8")
            self.max_size = struct.unpack("I", s.read(4))[0]
            regex_len = struct.unpack("I", s.read(4))[0]
            if regex_len > 0:
                self.regex = re.compile(s.read(regex_len).decode("utf-8"))
            nb_choices = struct.unpack("I", s.read(4))[0]
            if nb_choices > 0:
                self.choices = []
                for _ in range(nb_choices):
                    choice_len = struct.unpack("I", s.read(4))[0]
                    self.choices.append(s.read(choice_len).decode("utf-8"))

        def self_from_config(self, c: ConfigObject) -> None:
            if "encoding" in c:
                self.encoding = c.get_str("encoding")
            if "max_size" in c:
                self.max_size = c.get_int("max_size")
            if "choices" in c:
                self.choices = c.get_array("choices")
            if "regex" in c:
                self.regex = re.compile(c.get_str("regex"))

        def self_to_config(self, c: ConfigObject) -> None:
            if self.encoding != "utf-8":
                c["encoding"] = self.encoding
            if self.max_size != 0:
                c["max_size"] = self.max_size
            if self.choices is not None:
                c["choices"] = self.choices
            if self.regex is not None:
                c["regex"] = self.regex.pattern
    class Bool(ArgType):
        def value_from_config(self, v: ConfigValue) -> bool:
            if isinstance(v, bool):
                return v
            raise ConfigValidationError("Not a boolean")

        def value_from_str(self, v: str) -> int:
            v = v.lower().strip()
            if v in ["true", "1", "y", "yes", "high"]:
                return True
            if v in ["false", "0", "n", "no", "low"]:
                return False
            raise ConfigValidationError("Not a boolean")

        def value_from_stream(self, s: io.RawIOBase) -> bool:
            return struct.unpack("?", s.read(1))[0]

        def value_to_stream(self, v: bool, s: io.RawIOBase) -> None:
            s.write(struct.pack("?", v))

        def self_to_stream(self, s: io.RawIOBase) -> None:
            pass

        def self_from_stream(self, s: io.RawIOBase) -> None:
            pass

        def self_from_config(self, c: ConfigObject) -> None:
            pass

        def self_to_config(self, c: ConfigObject) -> None:
            pass # No specific attributes to dump

    class Numeric(ArgType, ABC):
        def __init__(
            self,
            help: str | None,
            min: float | int,
            max: float | int,
        ):
            super().__init__(help)
            self.min = min
            self.max = max

        def self_to_stream(self, s: io.RawIOBase) -> None:
            self.value_to_stream(self.min, s)
            self.value_to_stream(self.max, s)

        def self_from_stream(self, s: io.RawIOBase) -> None:
            self.min = self.value_from_stream(s)
            self.max = self.value_from_stream(s)

    class Float(Numeric, ABC):
        def value_from_config(self, v: ConfigValue) -> float:
            # self.min and self.max are guaranteed to be non-None after __init__
            if not isinstance(v, (int, float)):
                raise ConfigValidationError(f"{type(self).__name__} value must be a number")
            if v < self.min or v > self.max:
                raise ConfigValidationError(f"{type(self).__name__} value must be between {self.min} and {self.max}")
            return float(v)

        def __init__(self, help = None, min: float | None = None, max: float | None = None):
            super().__init__(help, min, max)
            if self.min is None:
                self.min = -math.inf
            if self.max is None:
                self.max = math.inf

        def self_from_config(self, c: ConfigObject) -> None:
            self.min = c.get_float_or("min", -math.inf)
            self.max = c.get_float_or("max", math.inf)

        def self_to_config(self, c: ConfigObject) -> None:
            if self.min != -math.inf:
                c["min"] = self.min
            if self.max != math.inf:
                c["max"] = self.max

        def value_from_str(self, v: str) -> float:
            return float(v)

    class Int(Numeric, ABC):
        _default_min: int = None
        _default_max: int = None

        def __init__(self, help, min, max):
            assert(self._default_min is not None)
            assert(self._default_max is not None)
            super().__init__(help,
                min if min is not None else self._default_min,
                max if max is not None else self._default_max,
            )

        def value_from_config(self, v: ConfigValue) -> int:
            if not isinstance(v, int):
            # self.min and self.max are guaranteed to be non-None after __init__
                raise ConfigValidationError(f"{type(self).__name__} value must be an integer")
            if v < self.min or v > self.max:
                raise ConfigValidationError(f"{type(self).__name__} value must be between {self.min} and {self.max}")
            return v

        def self_from_config(self, c: ConfigObject) -> None:
            self.min = c.get_int_or("min", self._default_min)
            self.max = c.get_int_or("max", self._default_max)

        def value_from_str(self, v: str) -> int:
            return int(v)

        def self_to_config(self, c: ConfigObject) -> None:
            if self.min != self._default_min:
                c["min"] = self.min
            if self.max != self._default_max:
                c["max"] = self.max

    class F16(Float):
        def __init__(self, help = None, min: float | None = None, max: float | None = None):
            super().__init__(help, min or -math.inf, max or math.inf)

        def value_from_stream(self, s: io.RawIOBase) -> float:
            return struct.unpack("e", s.read(4))[0]

        def value_to_stream(self, v: float, s: io.RawIOBase) -> None:
            s.write(struct.pack("e", v))

    class F32(Float):
        def __init__(self, help = None, min: float | None = None, max: float | None = None):
            super().__init__(help, min, max)

        def value_from_stream(self, s: io.RawIOBase) -> float:
            return struct.unpack("f", s.read(4))[0]

        def value_to_stream(self, v: float, s: io.RawIOBase) -> None:
            s.write(struct.pack("f", v))

    class F64(Float):
        def __init__(self, help = None, min: float | None = None, max: float | None = None):
            super().__init__(help, min, max)

        def value_from_stream(self, s: io.RawIOBase) -> float:
            return struct.unpack("d", s.read(8))[0]

        def value_to_stream(self, v: float, s: io.RawIOBase) -> None:
            s.write(struct.pack("d", v))

    class U8(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = 0
            self._default_max = 0xFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("B", s.read(1))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("B", v))

    class U16(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = 0
            self._default_max = 0xFFFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("H", s.read(2))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("H", v))

    class U32(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = 0
            self._default_max = 0xFFFFFFFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("I", s.read(4))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", v))

    class U64(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = 0
            self._default_max = 0xFFFFFFFFFFFFFFFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("Q", s.read(8))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("Q", v))

    class I8(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = -0x80
            self._default_max = 0x7F
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("b", s.read(1))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("b", v))

    class I16(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = -0x8000
            self._default_max = 0x7FFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("h", s.read(2))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("h", v))

    class I32(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = -0x80000000
            self._default_max = 0x7FFFFFFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("i", s.read(4))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("i", v))

    class I64(Int):
        def __init__(self, help = None, min_value: float | None = None, max_value: float | None = None):
            self._default_min = -0x8000000000000000
            self._default_max = 0x7FFFFFFFFFFFFFFF
            super().__init__(help, min_value, max_value)

        def value_from_stream(self, s: io.RawIOBase) -> int:
            return struct.unpack("q", s.read(8))[0]

        def value_to_stream(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("q", v))

    class Enum(ArgType):
        def __init__(
            self,
            enum_type: type[IntEnum],
            subargs: dict[IntEnum, ArgType] = {},
            help: str | None = None,
        ):
            super().__init__(help)
            self.enum_type = enum_type

        def value_from_config(self, v: ConfigValue) -> IntEnum:
            if isinstance(v, str):
                try:
                    return self.enum_type[v]
                except KeyError:
                    raise ConfigValidationError(f"Invalid enum value: {v}")
            elif isinstance(v, int):
                try:
                    return self.enum_type(v)
                except ValueError:
                    raise ConfigValidationError(f"Invalid enum value: {v}")
            else:
                raise ConfigValidationError("Enum value must be a string or integer")

        def value_from_str(self, v: str) -> IntEnum:
            return self.enum_type[v]

        def value_from_stream(self, s: io.RawIOBase) -> IntEnum:
            index = struct.unpack("I", s.read(4))[0]
            return self.enum_type(index)

        def value_to_stream(self, v: IntEnum, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", v.value))

        def self_to_stream(self, s: io.RawIOBase) -> None:
            # Serialize enum type name and members
            type_name = self.enum_type.__name__.encode("utf-8")
            s.write(struct.pack("I", len(type_name)))
            s.write(type_name)
            members = list(self.enum_type)
            s.write(struct.pack("I", len(members)))
            for member in members:
                member_name = member.name.encode("utf-8")
                s.write(struct.pack("I", len(member_name)))
                s.write(member_name)
                s.write(struct.pack("I", member.value))

        def self_from_stream(self, s: io.RawIOBase) -> None:
            # Note: Deserializing enum type dynamically would be complex
            # This is a simplified implementation
            type_name_len = struct.unpack("I", s.read(4))[0]
            s.read(type_name_len)  # Skip type name
            num_members = struct.unpack("I", s.read(4))[0]
            for _ in range(num_members):
                member_name_len = struct.unpack("I", s.read(4))[0]
                s.read(member_name_len)  # Skip member name
                struct.unpack("I", s.read(4))  # Skip member value

        def self_from_config(self, c: ConfigObject) -> None:
            # Enum type should be provided in constructor, nothing to do here
            pass

        def self_to_config(self, c: ConfigObject) -> None:
            pass # Enum type is provided at construction, not serialized to config

    # Reference to a device
    class Component(ArgType):
        def __init__(self, base_type: type[Peripheral], components: Registry[Peripheral]):
            self.components = components
            self.base_type = base_type

        def value_from_config(self, v: ConfigValue) -> Any:
            if not isinstance(v, str):
                raise ConfigValidationError("Component reference must be a string")
            component = self.components.get(v)
            if component is None:
                raise ConfigValidationError(f"Component '{v}' not found")
            if not isinstance(component, self.base_type):
                raise ConfigValidationError(
                    f"Component '{v}' is not of type {self.base_type.__name__}"
                )
            return component

        def value_from_str(self, v: str) -> int:
            component = self.components.get(v)
            if not isinstance(component, self.base_type):
                raise ConfigValidationError("Bad driver type")
            return component

        def value_from_stream(self, s: io.RawIOBase) -> Any:
            raise NotImplementedError("Decoding of component reference is not implemented")

        def value_to_stream(self, v: Any, s: io.RawIOBase) -> None:
            raise NotImplementedError("Encoding of component reference is not implemented")

        def self_to_stream(self, s: io.RawIOBase) -> None:
            raise NotImplementedError(
                "Serialization of component reference is not implemented"
            )

        def self_from_stream(self, s: io.RawIOBase) -> None:
            raise NotImplementedError(
                "Deserialization of component reference is not implemented"
            )

        def self_from_config(self, c: ConfigObject) -> None:
            # Component references don't have configuration
            pass

        def self_to_config(self, c: ConfigObject) -> None:
            pass

    class OptionalComponent(Component):
        """Like Component, but accepts a missing/null config value (returns None).

        Use for dependencies a driver can function without (e.g. an optional
        illumination LED attached to a color sensor).
        """

        def value_from_config(self, v: ConfigValue) -> Any:
            if v is None or v == "":
                return None
            return super().value_from_config(v)

        def value_from_str(self, v: str) -> Any:
            if v == "" or v.lower() == "none":
                return None
            return super().value_from_str(v)


ID_TO_ARGTYPE: list[type[ArgType]] = [
    ArgTypes.I64,
    ArgTypes.I32,
    ArgTypes.I16,
    ArgTypes.I8,
    ArgTypes.U64,
    ArgTypes.U32,
    ArgTypes.U16,
    ArgTypes.U8,
    ArgTypes.F64,
    ArgTypes.F32,
    ArgTypes.String,
    ArgTypes.Array,
    ArgTypes.Struct,
    ArgTypes.Enum,
    ArgTypes.Bool
]

ARGTYPE_TO_ID: dict[type[ArgType], int] = {t: i for i, t in enumerate(ID_TO_ARGTYPE)}

NAME_TO_ARGTYPE: dict[str, type[ArgType]] = {
    "int":    ArgTypes.I64,
    "i64":    ArgTypes.I64,
    "i32":    ArgTypes.I32,
    "i16":    ArgTypes.I16,
    "i8":     ArgTypes.I8,
    "u64":    ArgTypes.U64,
    "u32":    ArgTypes.U32,
    "u16":    ArgTypes.U16,
    "u8":     ArgTypes.U8,
    "float":  ArgTypes.F64,
    "f64":    ArgTypes.F64,
    "f32":    ArgTypes.F32,
    "str":    ArgTypes.String,
    "array":  ArgTypes.Array,
    "struct": ArgTypes.Struct,
    "enum":   ArgTypes.Enum,
    "bool":   ArgTypes.Bool,
}

ARGTYPE_TO_NAME: dict[type[ArgType], str] = {t: n for n, t in NAME_TO_ARGTYPE.items()}


def argtype_from_config(config: ConfigObject) -> ArgType:
    type_name = config.get_str("type")
    if type_name not in NAME_TO_ARGTYPE:
        raise ValueError(f"Unknown argtype name '{type_name}'")
    argtype = NAME_TO_ARGTYPE[type_name]()
    argtype.self_from_config(config)
    return argtype


def argtype_to_config(argtype: ArgType) -> ConfigObject:
    config = ConfigObject()
    config["type"] = ARGTYPE_TO_NAME[type(argtype)]
    argtype.self_to_config(config)
    return config


def argtype_from_stream(s: io.RawIOBase) -> ArgType:
    argtype_id = s.read(1)[0]
    argtype = ID_TO_ARGTYPE[argtype_id]
    arg = argtype()
    arg.self_from_stream(s)
    return arg


def argtype_to_stream(argtype: ArgType, s: io.RawIOBase) -> None:
    argtype_id = ARGTYPE_TO_ID[type(argtype)]
    s.write(bytes([argtype_id]))
    argtype.self_to_stream(s)
