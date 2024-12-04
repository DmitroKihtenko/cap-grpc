import asyncio
from logging import getLogger

import grpc
from google.protobuf import descriptor_pool
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message_factory import MessageFactory
from grpc import RpcMethodHandler
from grpc.aio import Server
from grpc_reflection.v1alpha import reflection

from protobuf.types import ProtoType
from server.helpers import ProtoObjectResolver
from config.model import ServerConfig
from server.processors import ResponseProcessor
from protobuf.definitions import ServiceData, ProtoFileStructure
from utils import read_file, get_relative_abs_path


logger = getLogger(__name__)


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


def check_methods(
    structure: ProtoFileStructure, server_config: ServerConfig,
):
    if server_config.mocks is None:
        return

    unknown_services = set()
    unknown_methods = {}
    for service_name, methods in server_config.mocks.root.items():
        if service_name not in structure.services:
            unknown_services.add(service_name)
        else:
            for method_name in methods.keys():
                if method_name not in structure.services[service_name].methods:
                    if service_name not in unknown_methods:
                        unknown_methods[service_name] = set()
                    unknown_methods[service_name].add(method_name)

    if len(unknown_services) > 0:
        logger.warning(
            f"Services were not described in Protobuf file/s for server "
            f"'{server_config.alias}': '{', '.join(unknown_services)}'"
        )

    if len(unknown_methods) > 0:
        methods_strings = []
        for service_name, methods in unknown_methods.items():
            methods_strings.append(
                f"'{service_name}' -> '{"', '".join(methods)}'"
            )
        logger.warning(
            f"Methods were not described in Protobuf file/s for server "
            f"'{server_config.alias}':\n{"\n".join(methods_strings)}"
        )


class GRPCServerConfigurer:
    SERVICER_FORMAT = "{}MockServicer"

    def __init__(
        self,
        object_resolver: ProtoObjectResolver,
        response_processor: ResponseProcessor,
        server_config: ServerConfig,
    ):
        self._obj_resolver = object_resolver
        self._response_processor = response_processor
        self._server_config = server_config
        self._pool = descriptor_pool.Default()
        self._factory = MessageFactory(self._pool)

    @property
    def object_resolver(self) -> ProtoObjectResolver:
        return self._obj_resolver

    @object_resolver.setter
    def object_resolver(self, object_resolver: ProtoObjectResolver):
        self._obj_resolver = object_resolver

    @property
    def server_config(self) -> ServerConfig:
        return self._server_config

    @server_config.setter
    def server_config(self, server_config: ServerConfig):
        self._server_config = server_config

    @property
    def response_processor(self) -> ResponseProcessor:
        return self._response_processor

    @response_processor.setter
    def response_processor(self, mock_processor: ResponseProcessor):
        self._response_processor = mock_processor

    def _create_rpc_method_handlers(
        self, service_data: ServiceData,
    ) -> dict[str, RpcMethodHandler]:
        rpc_method_handlers = {}
        for method_data in service_data.methods.values():
            method_func = self._response_processor.generate_method_processor(
                service_data,
                method_data,
            )
            if method_func is None:
                logger.warning(
                    f"Error creating method '{method_data.name}' in service "
                    f"'{service_data.full_name}'"
                )

            in_data = self.object_resolver.summarized_structure.messages[
                method_data.input_message.name
            ]
            out_data = self.object_resolver.summarized_structure.messages[
                method_data.output_message.name
            ]
            in_type = self.object_resolver.get_message_type(in_data)
            out_type = self.object_resolver.get_message_type(out_data)
            if method_data.input_message.streaming:
                if method_data.output_message.streaming:
                    handler_creator = grpc.stream_stream_rpc_method_handler
                else:
                    handler_creator = grpc.stream_unary_rpc_method_handler
            else:
                if method_data.output_message.streaming:
                    handler_creator = grpc.unary_stream_rpc_method_handler
                else:
                    handler_creator = grpc.unary_unary_rpc_method_handler

            rpc_method_handlers[
                method_data.name
            ] = handler_creator(
                method_func,
                request_deserializer=in_type.FromString,
                response_serializer=out_type.SerializeToString,
            )
        return rpc_method_handlers

    def build_server(
        self,
        config_file_dir: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> Server:
        check_methods(
            self.object_resolver.summarized_structure,
            self.server_config,
        )

        resolver = self._obj_resolver
        server = grpc.aio.server()

        for socket_data in self.server_config.sockets:
            if socket_data.certificates is None:
                server.add_insecure_port(socket_data.socket)
            else:
                cert_config = socket_data.certificates
                cert_data = read_file(get_relative_abs_path(
                    config_file_dir, cert_config.certificate,
                ))
                key_data = read_file(get_relative_abs_path(
                    config_file_dir, cert_config.certificate,
                ))
                root_cert_data = None
                if cert_config.root_certificate is not None:
                    root_cert_data = read_file(get_relative_abs_path(
                        config_file_dir, cert_config.root_certificate,
                    ))
                credentials = grpc.ssl_server_credentials(
                    [(key_data, cert_data)],
                    root_cert_data,
                    root_cert_data is not None,
                )
                server.add_secure_port(socket_data.socket, credentials)

        for service_data in resolver.summarized_structure.services.values():
            method_handlers = self._create_rpc_method_handlers(service_data)
            services_handler = grpc.method_handlers_generic_handler(
                service_data.full_name, method_handlers)
            server.add_generic_rpc_handlers((services_handler,))
            server.add_registered_method_handlers(
                service_data.full_name, method_handlers
            )

        if self.server_config.reflection_enabled:
            reflection_services = [
                reflection.SERVICE_NAME,
                *resolver.summarized_structure.services.keys(),
            ]
            reflection.enable_server_reflection(
                reflection_services,
                server,
                self._obj_resolver.get_descriptor_pool(),
            )

        if loop is not None:
            server._loop = loop

        return server
