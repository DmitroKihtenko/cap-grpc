import copy
import inspect
from types import ModuleType
from typing import Callable

from google.protobuf.internal.enum_type_wrapper import EnumTypeWrapper
from grpc import StatusCode

from model.config import GRPCErrorCode
from protobuf.definitions import (
    GeneratedData, ProtoFileStructure, ServiceData, MessageData, EnumData
)


def get_grpc_status_code(value: GRPCErrorCode) -> StatusCode:
    for enum_value in StatusCode:
        if enum_value.value[0] == value:
            return enum_value
    return StatusCode.UNKNOWN


class ProtoObjectResolver:
    SERVICER_FORMAT = "{}Servicer"
    STUB_FORMAT = "{}Stub"
    SERVICER_FUNCTIONS_FORMAT = "add_{}Servicer_to_server"

    def __init__(
        self,
        generated_data: GeneratedData,
        grpc_modules: dict[str, ModuleType],
        proto_structures: dict[str, ProtoFileStructure],
    ):
        self._generated_data = generated_data
        self._modules = grpc_modules
        self._structures = proto_structures
        self._summarized_structure = self._summarize_proto_structure()

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
    def generated_data(self) -> GeneratedData:
        return self._generated_data

    @property
    def grpc_modules(self) -> dict[str, ModuleType]:
        return self._modules

    @property
    def structures(self) -> dict[str, ProtoFileStructure]:
        return self._structures

    @property
    def summarized_structure(self) -> ProtoFileStructure:
        return self._summarized_structure

    def get_stub_type(self, service_data: ServiceData) -> type | None:
        object_data = None
        target_proto_file = None

        for proto_file, structure in self._structures.items():
            if service_data.full_name in structure.services:
                target_proto_file = proto_file
        if target_proto_file is None:
            return None

        spec_names = self._generated_data.proto_file_to_source.get(
            target_proto_file
        )
        if spec_names is None:
            return None

        for spec_name in spec_names:
            if spec_name not in self._modules:
                continue
            object_data = getattr(
                self._modules[spec_name],
                self.STUB_FORMAT.format(service_data.name),
                None,
            )
            if not inspect.isclass(object_data):
                object_data = None
            if object_data is not None:
                break

        return object_data

    def get_servicer_type(self, service_data: ServiceData) -> type | None:
        object_data = None
        target_proto_file = None

        for proto_file, structure in self._structures.items():
            if service_data.full_name in structure.services:
                target_proto_file = proto_file
        if target_proto_file is None:
            return None

        spec_names = self._generated_data.proto_file_to_source.get(
            target_proto_file
        )
        if spec_names is None:
            return None

        for spec_name in spec_names:
            if spec_name not in self._modules:
                continue
            object_data = getattr(
                self._modules[spec_name],
                self.SERVICER_FORMAT.format(service_data.name),
                None,
            )
            if not inspect.isclass(object_data):
                object_data = None
            if object_data is not None:
                break

        return object_data

    def get_message_type(self, message_data: MessageData) -> type | None:
        object_data = None
        target_proto_file = None

        for proto_file, structure in self._structures.items():
            if message_data.full_name in structure.messages:
                target_proto_file = proto_file
        if target_proto_file is None:
            return None

        spec_names = self._generated_data.proto_file_to_source.get(
            target_proto_file
        )
        if spec_names is None:
            return None

        parent_full_name = message_data.message
        attributes = [message_data.name]
        while parent_full_name is not None:
            new_message_data = self.summarized_structure.messages[
                parent_full_name
            ]
            parent_full_name = new_message_data.message
            attributes.append(new_message_data.name)
        attributes.reverse()

        source = None
        for spec_name in spec_names:
            if spec_name not in self._modules:
                continue
            source = self._modules[spec_name]

            for attribute in attributes:
                source = getattr(source, attribute, None)
                if not inspect.isclass(source):
                    source = None
                if source is None:
                    break
            if source is not None:
                break
        if source is not None:
            object_data = source

        return object_data

    def get_enum_type(
        self,
        enum_data: EnumData,
    ) -> EnumTypeWrapper | None:
        object_data = None
        target_proto_file = None

        for proto_file, structure in self._structures.items():
            if enum_data.full_name in structure.enums:
                target_proto_file = proto_file
        if target_proto_file is None:
            return None

        spec_names = self._generated_data.proto_file_to_source.get(
            target_proto_file
        )
        if spec_names is None:
            return None

        message_full_name = enum_data.message
        attributes = [enum_data.name]
        while message_full_name is not None:
            message_data = self.summarized_structure.messages[
                message_full_name
            ]
            message_full_name = message_data.message
            attributes.append(message_data.name)
        attributes.reverse()

        source = None
        for spec_name in spec_names:
            if spec_name not in self._modules:
                continue
            source = self._modules[spec_name]

            for attribute in attributes:
                source = getattr(source, attribute, None)
                if source is None:
                    break
            if source is not None:
                break
        if source is not None:
            object_data = source

        return object_data

    def get_servicer_function(self, service_data: ServiceData) -> Callable | None:
        object_data = None
        target_proto_file = None

        for proto_file, structure in self._structures.items():
            if service_data.full_name in structure.services:
                target_proto_file = proto_file
        if target_proto_file is None:
            return None

        spec_names = self._generated_data.proto_file_to_source.get(
            target_proto_file
        )
        if spec_names is None:
            return None

        for spec_name in spec_names:
            if spec_name not in self._modules:
                continue
            object_data = getattr(
                self._modules[spec_name],
                self.SERVICER_FUNCTIONS_FORMAT.format(service_data.name),
                None,
            )
            if not inspect.isfunction(object_data):
                object_data = None
            if object_data is not None:
                break

        return object_data
