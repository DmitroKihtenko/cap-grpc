from ctypes import c_double, c_float, c_int64, c_uint64, c_int32, c_uint32
from enum import Enum
from typing import Callable, Any

from pydantic import BaseModel


class GRPCType(str, Enum):
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


class TypeData(BaseModel):
    python_type: type
    converter: Callable
    default_value: Any


GRPC_PYTHON_TYPES = {
    GRPCType.DOUBLE: TypeData(
        python_type=int,
        converter=lambda v: c_double(int(v)).value,
        default_value=0
    ),
    GRPCType.FLOAT: TypeData(
        python_type=int,
        converter=lambda v: c_float(int(v)).value,
        default_value=0
    ),
    GRPCType.INT64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    GRPCType.UINT64: TypeData(
        python_type=int,
        converter=lambda v: c_uint64(int(v)).value,
        default_value=0
    ),
    GRPCType.INT32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    GRPCType.FIXED64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    GRPCType.FIXED32: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    GRPCType.BOOL: TypeData(
        python_type=bool,
        converter=lambda v: bool(v),
        default_value=False
    ),
    GRPCType.STRING: TypeData(
        python_type=str,
        converter=lambda v: v if isinstance(v, str) else str(v),
        default_value=""
    ),
    GRPCType.GROUP: None,
    GRPCType.MESSAGE: None,
    GRPCType.BYTES: TypeData(
        python_type=bytes,
        converter=lambda v: v if isinstance(v, bytes) else bytes(v),
        default_value=0
    ),
    GRPCType.UINT32: TypeData(
        python_type=int,
        converter=lambda v: c_uint32(int(v)).value,
        default_value=0
    ),
    GRPCType.ENUM: None,
    GRPCType.SFIXED32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    GRPCType.SFIXED64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
    GRPCType.SINT32: TypeData(
        python_type=int,
        converter=lambda v: c_int32(int(v)).value,
        default_value=0
    ),
    GRPCType.SINT64: TypeData(
        python_type=int,
        converter=lambda v: c_int64(int(v)).value,
        default_value=0
    ),
}

SimpleProtoType = str | float | int | bool | bytes
