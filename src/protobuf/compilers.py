import tempfile

from google.protobuf import descriptor_pb2 as proto
from google.protobuf.descriptor import (
    Descriptor,
    FieldDescriptor,
    EnumDescriptor,
    EnumValueDescriptor,
    ServiceDescriptor, MethodDescriptor,
)
from google.protobuf.descriptor_pool import DescriptorPool
from grpc_tools import protoc

from constants import DESCRIPTOR_TEMP_FILENAME
from protobuf.types import ProtoType
from protobuf.definitions import (
    InMethodMessageData,
    MethodData,
    EnumField,
    MessageField,
    EnumData,
    MessageData,
    ServiceData,
    ProtoFileStructure,
    ProtoFilesPaths,
    PropertyLabel,
)
from utils import read_file_bytes, get_relative_abs_path

G_PRTBF_T_INDEX_TO_TYPE = {
    FieldDescriptor.TYPE_DOUBLE: ProtoType.DOUBLE,
    FieldDescriptor.TYPE_FLOAT: ProtoType.FLOAT,
    FieldDescriptor.TYPE_INT64: ProtoType.INT64,
    FieldDescriptor.TYPE_UINT64: ProtoType.UINT64,
    FieldDescriptor.TYPE_INT32: ProtoType.INT32,
    FieldDescriptor.TYPE_FIXED64: ProtoType.FIXED64,
    FieldDescriptor.TYPE_FIXED32: ProtoType.FIXED32,
    FieldDescriptor.TYPE_BOOL: ProtoType.BOOL,
    FieldDescriptor.TYPE_STRING: ProtoType.STRING,
    FieldDescriptor.TYPE_GROUP: ProtoType.GROUP,
    FieldDescriptor.TYPE_MESSAGE: ProtoType.MESSAGE,
    FieldDescriptor.TYPE_BYTES: ProtoType.BYTES,
    FieldDescriptor.TYPE_UINT32: ProtoType.UINT32,
    FieldDescriptor.TYPE_ENUM: ProtoType.ENUM,
    FieldDescriptor.TYPE_SFIXED32: ProtoType.SFIXED32,
    FieldDescriptor.TYPE_SFIXED64: ProtoType.SFIXED64,
    FieldDescriptor.TYPE_SINT32: ProtoType.SINT32,
    FieldDescriptor.TYPE_SINT64: ProtoType.SINT64,
}


def update_if_map(message_data: MessageData):
    is_map = False
    if message_data.name.endswith("Entry"):
        if len(message_data.fields) == 2:
            if message_data.fields[0].name in {
                "key", "value"
            } and message_data.fields[1].name in {"key", "value"}:
                is_map = True
    if is_map:
        message_data.is_map = True


def generate_descriptor_pool(proto_paths: ProtoFilesPaths):
    pool = DescriptorPool()

    with tempfile.TemporaryDirectory() as dir_name:
        descriptor_abs = get_relative_abs_path(dir_name, DESCRIPTOR_TEMP_FILENAME)
        command_code = protoc.main((
            "",
            f"-I{proto_paths.base_dir_abs}",
            f"--descriptor_set_out={descriptor_abs}",
            *proto_paths.proto_files_abs,
        ))
        if command_code != 0:
            raise RuntimeError("Proto files compilation failed")

        descriptor_set = proto.FileDescriptorSet()
        data = read_file_bytes(descriptor_abs)
        descriptor_set.ParseFromString(data)
        for file_proto in descriptor_set.file:
            pool.Add(file_proto)
    return pool


class StructureParser:
    def __init__(
        self,
        pool: DescriptorPool,
        proto_paths: ProtoFilesPaths,
    ):
        self._descriptor_pool = pool
        self._proto_paths = proto_paths

    @property
    def descriptor_pool(self) -> DescriptorPool:
        return self._descriptor_pool

    @property
    def proto_paths(self) -> ProtoFilesPaths:
        return self._proto_paths

    def _parse_message(
        self,
        message_data: Descriptor,
        messages_result: dict[str, MessageData],
        enums_result: dict[str, EnumData]
    ):
        if message_data.full_name in messages_result:
            return

        fields = []
        nested_messages = []
        nested_enums = []
        parent_message = None

        if message_data.containing_type is not None:
            parent_message = message_data.containing_type.full_name

        for message_descriptor in message_data.nested_types:
            message_descriptor: Descriptor
            nested_messages.append(message_descriptor.full_name)

        for enum_descriptor in message_data.enum_types:
            enum_descriptor: EnumDescriptor
            nested_enums.append(enum_descriptor.full_name)

        result_message = MessageData(
            name=message_data.name,
            parent_message=parent_message,
            nested_messages=nested_messages,
            nested_enums=nested_enums,
            full_name=message_data.full_name,
            fields=[],
        )
        messages_result[message_data.full_name] = result_message

        for field_name, field in message_data.fields_by_name.items():
            field: FieldDescriptor
            nested_message = None
            nested_enum = None
            default = None
            is_map = False

            label = PropertyLabel.OPTIONAL
            if field.label == field.LABEL_REQUIRED:
                label = PropertyLabel.REQUIRED
            elif field.label == field.LABEL_REPEATED:
                label = PropertyLabel.REPEATED

            if field.message_type is not None:
                nested_message = field.message_type.full_name
                self._parse_message(
                    field.message_type, messages_result, enums_result
                )

            if field.enum_type is not None:
                nested_enum = field.enum_type.full_name
                self._parse_enum(field.enum_type, enums_result)

            if field.has_default_value:
                default = field.default_value

            if nested_message is not None:
                if nested_message in messages_result:
                    is_map = messages_result[nested_message].is_map

            fields.append(MessageField(
                message_type=nested_message,
                enum_type=nested_enum,
                name=field.name,
                simple_type=G_PRTBF_T_INDEX_TO_TYPE[field.type],
                number=field.number,
                default=default,
                is_map=is_map,
                label=label,
            ))
        result_message.fields = fields
        update_if_map(result_message)

    def _parse_enum(
        self, enum_data: EnumDescriptor, result: dict[str, EnumData]
    ):
        fields = []
        message = None
        if enum_data.containing_type is not None:
            message = enum_data.containing_type.full_name

        for value_name, value_data in enum_data.values_by_name.items():
            value_data: EnumValueDescriptor
            fields.append(EnumField(
                name=value_name,
                number=value_data.number,
            ))
        result[enum_data.full_name] = EnumData(
            name=enum_data.name,
            parent_message=message,
            full_name=enum_data.full_name,
            fields=fields,
        )

    def get_structures(self) -> dict[str, ProtoFileStructure]:
        pool = self.descriptor_pool
        result = {}

        for file_relative in self.proto_paths.get_relative_map().values():
            try:
                file_descriptor = pool.FindFileByName(file_relative)
            except KeyError as e:
                raise KeyError(f"Required component not found: {e}")
            services_result = {}
            messages_result = {}
            enums_result = {}

            for name, service_data in file_descriptor.services_by_name.items():
                service_data: ServiceDescriptor
                methods_result = {}

                for method in service_data.methods:
                    method: MethodDescriptor
                    methods_result[method.name] = MethodData(
                        name=method.name,
                        input_message=InMethodMessageData(
                            name=method.input_type.full_name,
                            streaming=method.client_streaming,
                        ),
                        output_message=InMethodMessageData(
                            name=method.output_type.full_name,
                            streaming=method.server_streaming,
                        ),
                    )
                services_result[service_data.full_name] = ServiceData(
                    name=service_data.name,
                    full_name=service_data.full_name,
                    methods=methods_result,
                )

            for message_data in file_descriptor.message_types_by_name.values():
                self._parse_message(message_data, messages_result, enums_result)

            for enum_data in file_descriptor.enum_types_by_name.values():
                self._parse_enum(enum_data, enums_result)

            result[file_descriptor.name] = ProtoFileStructure(
                package=file_descriptor.package or None,
                messages=messages_result,
                services=services_result,
                enums=enums_result,
            )
        return result
