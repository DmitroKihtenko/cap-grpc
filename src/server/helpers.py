import copy
import logging
from typing import Type

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.descriptor_pool import DescriptorPool
from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from google.protobuf.message import Message
from google.protobuf.message_factory import GetMessageClass
from grpc import StatusCode

from config.model import GRPCErrorCode
from protobuf.definitions import (
    ProtoFileStructure,
    MessageData,
    EnumData,
)
from protobuf.types import ProtoType

logger = logging.getLogger(__name__)


def get_grpc_status_code(value: GRPCErrorCode) -> StatusCode:
    for enum_value in StatusCode:
        if enum_value.value[0] == value:
            return enum_value
    return StatusCode.UNKNOWN


PROTO_TYPE_INTERNAL_DATA = {
    ProtoType.DOUBLE: FieldDescriptor.TYPE_DOUBLE,
    ProtoType.FLOAT: FieldDescriptor.TYPE_FLOAT,
    ProtoType.INT64: FieldDescriptor.TYPE_INT64,
    ProtoType.UINT64: FieldDescriptor.TYPE_UINT64,
    ProtoType.INT32: FieldDescriptor.TYPE_INT32,
    ProtoType.FIXED64: FieldDescriptor.TYPE_FIXED64,
    ProtoType.FIXED32: FieldDescriptor.TYPE_FIXED32,
    ProtoType.BOOL: FieldDescriptor.TYPE_BOOL,
    ProtoType.STRING: FieldDescriptor.TYPE_STRING,
    ProtoType.GROUP: FieldDescriptor.TYPE_GROUP,
    ProtoType.MESSAGE: FieldDescriptor.TYPE_MESSAGE,
    ProtoType.BYTES: FieldDescriptor.TYPE_BYTES,
    ProtoType.UINT32: FieldDescriptor.TYPE_UINT32,
    ProtoType.ENUM: FieldDescriptor.TYPE_ENUM,
    ProtoType.SFIXED32: FieldDescriptor.TYPE_SFIXED32,
    ProtoType.SFIXED64: FieldDescriptor.TYPE_SFIXED64,
    ProtoType.SINT32: FieldDescriptor.TYPE_SINT32,
    ProtoType.SINT64: FieldDescriptor.TYPE_SINT64,
}


class ProtoObjectResolver:
    def __init__(
        self,
        proto_structures: dict[str, ProtoFileStructure],
        descriptor_pool: DescriptorPool,
    ):
        self._structures = proto_structures
        self._summarized_structure = self._summarize_proto_structure()

        self._descriptor_pool = descriptor_pool
        self._message_types = self._create_messages_types()
        self._enum_types = self._create_enum_types()

    def _summarize_proto_structure(self) -> ProtoFileStructure | None:
        result = None
        for structure in self._structures.values():
            if result is None:
                result = copy.deepcopy(structure)
            else:
                result.services.update(structure.services)
                result.messages.update(structure.messages)
                result.enums.update(structure.enums)
        return result

    @property
    def pool(self) -> DescriptorPool:
        return self._descriptor_pool

    @property
    def summarized_structure(self) -> ProtoFileStructure:
        return self._summarized_structure

    @property
    def structures(self) -> dict[str, ProtoFileStructure]:
        return self._structures

    def _create_messages_types(self) -> dict[str, Type[Message]]:
        result = {}
        for message_data in self.summarized_structure.messages.values():
            key = message_data.full_name
            result[key] = GetMessageClass(
                self._descriptor_pool.FindMessageTypeByName(key)
            )
        return result

    def _create_enum_types(self) -> dict[str, EnumTypeWrapper]:
        result = {}
        for enum_data in self.summarized_structure.enums.values():
            key = enum_data.full_name
            result[key] = EnumTypeWrapper(
                self._descriptor_pool.FindEnumTypeByName(key)
            )
        return result

    def get_descriptor_pool(self) -> DescriptorPool:
        return self._descriptor_pool

    def get_enum_type(self, enum_data: EnumData) -> EnumTypeWrapper:
        enum_type = self._enum_types.get(enum_data.full_name)
        if enum_type is None:
            message = (
                f"Error processing enum type '{enum_data.full_name}': "
                f"object descriptor not found"
            )

            logger.error(message)
            raise KeyError(message)
        return enum_type

    def get_message_type(self, message_data: MessageData) -> Type[Message]:
        descriptor = self._message_types.get(message_data.full_name)
        if descriptor is None:
            message = (
                f"Error processing message type '{message_data.full_name}': "
                f"object descriptor not found"
            )

            logger.error(message)
            raise KeyError(message)
        return descriptor
