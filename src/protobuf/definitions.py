import os
from enum import Enum

from pydantic import BaseModel

from protobuf.types import GRPCType


class ProtoFilesPaths(BaseModel):
    proto_files_abs: list[str]
    base_dir_abs: str

    def get_proto_files_relative(self) -> list[str]:
        result = []
        for file_path in self.proto_files_abs:
            result.append(os.path.relpath(file_path, self.base_dir_abs))
        return result


class GeneratedData(BaseModel):
    source_files: dict[str, str]
    proto_file_to_source: dict[str, set[str]]


class ParameterData(BaseModel):
    message: str


class MethodData(BaseModel):
    name: str
    input_param: ParameterData
    output_param: ParameterData


class EnumProperty(BaseModel):
    name: str
    number: int


class PropertyLabel(str, Enum):
    OPTIONAL = "optional"
    REPEATED = "repeated"
    REQUIRED = "required"


class MessageProperty(EnumProperty):
    nested_message: str | None = None
    nested_enum: str | None = None
    grpc_type: GRPCType
    label: PropertyLabel


class EnumData(BaseModel):
    name: str
    full_name: str
    message: str | None = None
    properties: list[EnumProperty]


class MessageData(BaseModel):
    name: str
    full_name: str
    message: str | None = None
    properties: list[MessageProperty]


class ServiceData(BaseModel):
    name: str
    full_name: str
    methods: dict[str, MethodData]


class ProtoFileStructure(BaseModel):
    package: str
    messages: dict[str, MessageData]
    services: dict[str, ServiceData]
    enums: dict[str, EnumData]
