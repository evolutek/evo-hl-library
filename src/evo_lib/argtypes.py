import io
import json
import struct
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from evo_lib.config import ConfigValidationError, ConfigValue

if TYPE_CHECKING:
    from evo_lib.component import Component
    from evo_lib.registry import Registry


class ArgType(ABC):
    def __init__(self, help: str | None = None):
        self.help = help

    def parse(self, v: str) -> Any:
        """Parse a string to the given argument type (usefull for CLI)."""
        return self.validate(json.load(v)) # Default implementation

    @abstractmethod
    def validate(self, v: ConfigValue) -> Any:
        """Check if a configuration value follow type's constraints and return
        the value in the correct type (usefull for config validation)."""
        pass

    @abstractmethod
    def decode(self, s: io.RawIOBase) -> Any:
        """Decode the value from a stream (usefull for communication protocol)."""
        pass

    @abstractmethod
    def encode(self, v: Any, s: io.RawIOBase) -> None:
        """Encode a value into a stream (usefull for communication protocol)."""
        pass

    def serialize(self, s: io.RawIOBase) -> None:
        """Serialize self type settings into a stream (usefull to send command
        format over a communication protocol)."""
        pass

    def deserialize(self, s: io.RawIOBase) -> None:
        """Deserialize self type from a stream (usefull to recv command format
        over a communication protocol)."""
        pass


class ArgTypes:
    class Struct(ArgType):
        def __init__(self, fields: list[tuple[str, ArgType]]):
            self.fields: list[tuple[str, ArgType]] = fields

        def decode(self, s: io.RawIOBase) -> dict[str,]:
            r = {}
            for fname, ftype in self.fields:
                r[fname] = ftype.decode(s)
            return r

        def encode(self, v: dict | object, s: io.RawIOBase) -> None:
            if isinstance(v, dict):
                for fname, ftype in self.fields:
                    ftype.encode(v[fname], s)
            else:
                for fname, ftype in self.fields:
                    ftype.encode(getattr(v, fname), s)

        def parse(self, v) -> object:
            r = {}
            if isinstance(v, dict):
                for fname, ftype in self.fields:
                    r[fname] = ftype.parse(v[fname])
            else:
                for fname, ftype in self.fields:
                    r[fname] = ftype.parse(getattr(v, fname))
            return r

    class Array(ArgType):
        def __init__(self, element_type: ArgType, max_size: int = 0):
            self.max_size = max_size
            self.element_type = element_type

        def decode(self, s: io.RawIOBase) -> list:
            length = struct.unpack("I", s.read(4))[0]
            result = []
            for _ in range(length):
                result.append(self.element_type.decode(s))
            return result

        def encode(self, v: list, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", len(v)))
            for e in v:
                self.element_type.encode(e, s)

    class Bytes(ArgType):
        def __init__(self, max_size: int = 0):
            self.max_size = max_size

        def decode(self, s: io.RawIOBase) -> bytes:
            size = struct.unpack("I", s.read(4))[0]
            return s.read(size)

        def encode(self, v: bytes, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", len(v)))
            s.write(v)

    class String(ArgType):
        def __init__(self, encoding: str = "utf8", max_size: int = 0):
            self.encoding = encoding
            self.max_size = max_size

        def parse(self, v: str) -> int:
            return str(v)

        def decode(self, s: io.RawIOBase) -> str:
            size = struct.unpack("I", s.read(4))[0]
            return s.read(size).decode(self.encoding)

        def encode(self, v: str, s: io.RawIOBase) -> None:
            b = v.encode(self.encoding)
            s.write(struct.pack("I", len(b)))
            s.write(b)

    class Bool(ArgType):
        def parse(self, v: str, subargs: dict[bool, ArgType] = {}) -> int:
            v = v.lower().strip()
            if v in ["true", "1", "y", "yes", "high"]:
                return True
            if v in ["false", "0", "n", "no", "low"]:
                return False
            raise ConfigValidationError("Not a boolean")

        def decode(self, s: io.RawIOBase) -> bool:
            return struct.unpack("?", s.read(1))[0]

        def encode(self, v: bool, s: io.RawIOBase) -> None:
            s.write(struct.pack("?", v))

    class F32(ArgType):
        def parse(self, v: str) -> float:
            return float(v)

        def decode(self, s: io.RawIOBase) -> float:
            return struct.unpack("f", s.read(4))[0]

        def encode(self, v: float, s: io.RawIOBase) -> None:
            s.write(struct.pack("f", v))

    class F64(ArgType):
        def parse(self, v: str) -> float:
            return float(v)

        def decode(self, s: io.RawIOBase) -> float:
            return struct.unpack("d", s.read(8))[0]

        def encode(self, v: float, s: io.RawIOBase) -> None:
            s.write(struct.pack("d", v))

    class U8(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("B", s.read(1))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("B", v))

    class U16(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("H", s.read(2))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("H", v))

    class U32(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("I", s.read(4))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", v))

    class U64(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("Q", s.read(8))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("Q", v))

    class I8(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("b", s.read(1))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("b", v))

    class I16(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("h", s.read(2))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("h", v))

    class I32(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("i", s.read(4))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("i", v))

    class I64(ArgType):
        def parse(self, v: str) -> float:
            return int(v)

        def decode(self, s: io.RawIOBase) -> int:
            return struct.unpack("q", s.read(8))[0]

        def encode(self, v: int, s: io.RawIOBase) -> None:
            s.write(struct.pack("q", v))

    class Enumeration(ArgType):
        def __init__(self, enum_type: type[Enum], subargs: dict[Enum, ArgType] = {}):
            self.enum_type = enum_type

        def parse(self, v: str) -> Enum:
            return self.enum_type[v]

        def decode(self, s: io.RawIOBase) -> Enum:
            index = struct.unpack("I", s.read(4))[0]
            return self.values[index]

        def encode(self, v: Enum, s: io.RawIOBase) -> None:
            s.write(struct.pack("I", self.indexes[v]))

    # Reference to a device
    class Component(ArgType):
        def __init__(self, base_type: type[Component], components: Registry[Component]):
            self.components = components
            self.base_type = base_type

        def parse(self, v: str) -> int:
            component = self.components.get(v)
            if not isinstance(component, self.base_type):
                raise ConfigValidationError("Bad driver type")
            return component

        def decode(self, s: io.RawIOBase) -> Enum:
            raise NotImplementedError("Decoding of component reference is not implemented")

        def encode(self, v: Enum, s: io.RawIOBase) -> None:
            raise NotImplementedError("Encoding of component reference is not implemented")
