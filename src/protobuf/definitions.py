import os
from enum import Enum

from pydantic import BaseModel

from protobuf.types import ProtoType
from utils import SimpleType


class ProtoFilesPaths(BaseModel):
    proto_files_abs: list[str]
    base_dir_abs: str

    def get_relative_map(self) -> dict[str, str]:
        result = {}
        for file_path in self.proto_files_abs:
            result[file_path] = os.path.relpath(file_path, self.base_dir_abs)
        return result


class GeneratedData(BaseModel):
    source_files: dict[str, str]
    proto_file_to_source: dict[str, set[str]]


class InMethodMessageData(BaseModel):
    name: str
    streaming: bool = False


class MethodData(BaseModel):
    name: str
    input_message: InMethodMessageData
    output_message: InMethodMessageData


class EnumField(BaseModel):
    name: str
    number: int


class PropertyLabel(str, Enum):
    OPTIONAL = "optional"
    REPEATED = "repeated"
    REQUIRED = "required"


class MessageField(EnumField):
    message_type: str | None = None
    enum_type: str | None = None
    complex_type: str | None = None
    simple_type: ProtoType | None = None
    default: SimpleType | None = None
    is_map: bool = False
    label: PropertyLabel


class EnumData(BaseModel):
    name: str
    full_name: str
    parent_message: str | None = None
    fields: list[EnumField]


class MessageData(BaseModel):
    name: str
    full_name: str
    parent_message: str | None = None
    nested_messages: list[str] = []
    nested_enums: list[str] = []
    is_map: bool = False
    fields: list[MessageField]


class ServiceData(BaseModel):
    name: str
    full_name: str
    methods: dict[str, MethodData]


class ProtoFileStructure(BaseModel):
    package: str | None = None
    messages: dict[str, MessageData]
    services: dict[str, ServiceData]
    enums: dict[str, EnumData]
