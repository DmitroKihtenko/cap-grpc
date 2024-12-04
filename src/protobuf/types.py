from ctypes import c_double, c_float, c_int64, c_uint64, c_int32, c_uint32
from enum import Enum
from typing import Callable, Any

from pydantic import BaseModel


class ProtoType(str, Enum):
    DOUBLE = "double"
    FLOAT = "float"
    INT64 = "int64"
    UINT64 = "uint32"
    INT32 = "int32"
    FIXED64 = "fixed64"
    FIXED32 = "fixed32"
    BOOL = "bool"
    STRING = "string"
    GROUP = "group"
    MESSAGE = "message"
    BYTES = "bytes"
    UINT32 = "uint32"
    ENUM = "enum"
    SFIXED32 = "sfixed32"
    SFIXED64 = "sfixed64"
    SINT32 = "sint32"
    SINT64 = "sint64"

    @classmethod
    def contains_value(cls, value):
        return value in cls._value2member_map_


class TypeData(BaseModel):
    python_type: type
    converter: Callable
    default_value: Any


GRPC_PYTHON_TYPES = {
    ProtoType.DOUBLE: TypeData(
        python_type=int,
        converter=lambda v: c_double(int(v)).value,
        default_value=0
    ),
    ProtoType.FLOAT: TypeData(
        python_type=int,
        converter=lambda v: c_float(int(v)).value,
        default_value=0
    ),
    ProtoType.INT64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    ProtoType.UINT64: TypeData(
        python_type=int,
        converter=lambda v: c_uint64(int(v)).value,
        default_value=0
    ),
    ProtoType.INT32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    ProtoType.FIXED64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    ProtoType.FIXED32: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    ProtoType.BOOL: TypeData(
        python_type=bool,
        converter=lambda v: bool(v),
        default_value=False
    ),
    ProtoType.STRING: TypeData(
        python_type=str,
        converter=lambda v: v if isinstance(v, str) else str(v),
        default_value=""
    ),
    ProtoType.GROUP: None,
    ProtoType.MESSAGE: None,
    ProtoType.BYTES: TypeData(
        python_type=bytes,
        converter=lambda v: v if isinstance(v, bytes) else bytes(v),
        default_value=0
    ),
    ProtoType.UINT32: TypeData(
        python_type=int,
        converter=lambda v: c_uint32(int(v)).value,
        default_value=0
    ),
    ProtoType.ENUM: None,
    ProtoType.SFIXED32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    ProtoType.SFIXED64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    ProtoType.SINT32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    ProtoType.SINT64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
}

SimpleProtoType = str | float | int | bool | bytes
