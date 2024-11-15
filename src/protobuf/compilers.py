import os
import tempfile
from types import ModuleType

from google.protobuf import descriptor_pool
from google.protobuf.descriptor import (
    FileDescriptor,
    Descriptor,
    FieldDescriptor,
    EnumDescriptor,
    EnumValueDescriptor,
    ServiceDescriptor,
)

from grpc_tools import protoc

from protobuf.types import GRPCType
from protobuf.definitions import (
    ParameterData,
    MethodData,
    EnumProperty,
    MessageProperty,
    EnumData,
    MessageData,
    ServiceData,
    ProtoFileStructure,
    ProtoFilesPaths,
    GeneratedData,
    PropertyLabel,
)
from protobuf.importers import import_in_memory_module_code
from protobuf.utils import get_python_spec_by_proto_path
from utils import read_file

G_PRTBF_T_INDEX_TO_TYPE = {
    FieldDescriptor.TYPE_DOUBLE: GRPCType.DOUBLE,
    FieldDescriptor.TYPE_FLOAT: GRPCType.FLOAT,
    FieldDescriptor.TYPE_INT64: GRPCType.INT64,
    FieldDescriptor.TYPE_UINT64: GRPCType.UINT64,
    FieldDescriptor.TYPE_INT32: GRPCType.INT32,
    FieldDescriptor.TYPE_FIXED64: GRPCType.FIXED64,
    FieldDescriptor.TYPE_FIXED32: GRPCType.FIXED32,
    FieldDescriptor.TYPE_BOOL: GRPCType.BOOL,
    FieldDescriptor.TYPE_STRING: GRPCType.STRING,
    FieldDescriptor.TYPE_GROUP: GRPCType.GROUP,
    FieldDescriptor.TYPE_MESSAGE: GRPCType.MESSAGE,
    FieldDescriptor.TYPE_BYTES: GRPCType.BYTES,
    FieldDescriptor.TYPE_UINT32: GRPCType.UINT32,
    FieldDescriptor.TYPE_ENUM: GRPCType.ENUM,
    FieldDescriptor.TYPE_SFIXED32: GRPCType.SFIXED32,
    FieldDescriptor.TYPE_SFIXED64: GRPCType.SFIXED64,
    FieldDescriptor.TYPE_SINT32: GRPCType.SINT32,
    FieldDescriptor.TYPE_SINT64: GRPCType.SINT64,
}

def read_source_files(
    dir: str, files_suffixes: list[str], prefix: str | None = None
):
    result = {}

    for filename in os.listdir(dir):
        target_file_abs = os.path.join(dir, filename)
        if os.path.isdir(target_file_abs):
            result.update(read_source_files(
                target_file_abs, files_suffixes, filename
            ))
        else:
            for suffix in files_suffixes:
                if filename.endswith(suffix):
                    filepath = os.path.join(dir, filename)
                    key = filename
                    if prefix is not None:
                        key = f"{prefix}.{filename}"
                    result[key] = read_file(filepath)
    return result


class GRPCSourceGenerator:
    SOURCE_FILES_SUFFIXES = ["_pb2.py", "_pb2_grpc.py"]

    def __init__(self, proto_paths: ProtoFilesPaths):
        self._proto_paths = proto_paths

    @property
    def proto_paths(self) -> ProtoFilesPaths:
        return self._proto_paths

    def _read_source_files(self, dir: str, files_suffixes: list[str]):
        result = {}

        for filename in os.listdir(dir):
            if os.path.isdir(filename):
                return self._read_source_files(filename, files_suffixes)
            else:
                for suffix in files_suffixes:
                    if filename.endswith(suffix):
                        filepath = os.path.join(dir, filename)
                        result[filename] = read_file(filepath)
        return result

    def generate_source_files(self) -> GeneratedData:
        with tempfile.TemporaryDirectory() as temp_output_dir:
            command_code = protoc.main((
                "",
                f"-I{self.proto_paths.base_dir_abs}",
                f"--python_out={temp_output_dir}",
                f"--grpc_python_out={temp_output_dir}",
                *self.proto_paths.proto_files_abs,
            ))

            if command_code != 0:
                raise RuntimeError("Proto files compilation failed")

            result = read_source_files(
                temp_output_dir, self.SOURCE_FILES_SUFFIXES
            )
            proto_file_to_source = {}
            for path in self.proto_paths.get_proto_files_relative():
                proto_file_to_source[path] = get_python_spec_by_proto_path(
                    path
                )
            return GeneratedData(
                source_files=result,
                proto_file_to_source=proto_file_to_source
            )


class GRPCCompiler:
    def __init__(
        self,
        proto_paths: ProtoFilesPaths,
        generated_data: GeneratedData,
    ):
        self._proto_paths = proto_paths
        self._generated_data = generated_data
        self._proto_structure = {}

    @property
    def proto_structure(self) -> dict[str, ProtoFileStructure]:
        return self._proto_structure

    @property
    def proto_paths(self) -> ProtoFilesPaths:
        return self._proto_paths

    @property
    def generated_data(self) -> GeneratedData:
        return self._generated_data

    def _parse_message(
        self,
        message_data: Descriptor,
        messages_result: dict[str, MessageData],
        enums_result: dict[str, EnumData]
    ):
        message_data: Descriptor
        properties = []
        message = None
        if message_data.containing_type is not None:
            message = message_data.containing_type.full_name

        for field_name, field in message_data.fields_by_name.items():
            nested_message = None

            field: FieldDescriptor

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
            nested_enum = None
            if field.enum_type is not None:
                nested_enum = field.enum_type.full_name
                self._parse_enum(field.enum_type, enums_result)

            properties.append(MessageProperty(
                nested_message=nested_message,
                nested_enum=nested_enum,
                name=field.name,
                grpc_type=G_PRTBF_T_INDEX_TO_TYPE[field.type],
                number=field.number,
                label=label,
            ))
        messages_result[message_data.full_name] = MessageData(
            name=message_data.name,
            message=message,
            full_name=message_data.full_name,
            properties=properties,
        )

    def _parse_enum(
        self, enum_data: EnumDescriptor, result: dict[str, EnumData]
    ):
        properties = []
        message = None
        if enum_data.containing_type is not None:
            message = enum_data.containing_type.full_name

        for value_name, value_data in enum_data.values_by_name.items():
            value_data: EnumValueDescriptor
            properties.append(EnumProperty(
                name=value_name,
                number=value_data.number,
            ))
        result[enum_data.full_name] = EnumData(
            name=enum_data.name,
            message=message,
            full_name=enum_data.full_name,
            properties=properties,
        )

    def execute_files(self) -> dict[str, ModuleType]:
        result = import_in_memory_module_code(self.generated_data)
        pool = descriptor_pool.Default()

        for file_relative in self.proto_paths.get_proto_files_relative():
            file_descriptor: FileDescriptor = pool.FindFileByName(file_relative)
            services_result = {}
            messages_result = {}
            enums_result = {}

            for name, service_data in file_descriptor.services_by_name.items():
                service_data: ServiceDescriptor

                methods_result = {}

                for method in service_data.methods:
                    methods_result[method.name] = MethodData(
                        name=method.name,
                        input_param=ParameterData(
                            message=method.input_type.full_name
                        ),
                        output_param=ParameterData(
                            message=method.output_type.full_name
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

            self._proto_structure[file_relative] = ProtoFileStructure(
                package=file_descriptor.package,
                messages=messages_result,
                services=services_result,
                enums=enums_result,
            )
        return result
