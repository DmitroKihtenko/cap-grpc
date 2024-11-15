import asyncio

import grpc
from grpc.aio import Server, ServerInterceptor
from grpc_reflection.v1alpha import reflection

from server.helpers import ProtoObjectResolver
from model.config import ServerConfig
from server.processors import GRPCServerMockProcessor
from protobuf.definitions import ServiceData
from utils import read_file, get_path_relative_to_config


class GoogleGRPCServerConfigurer:
    CUSTOM_SERVICER_FORMAT = "{:s}MockServicer"

    def __init__(
        self,
        object_resolver: ProtoObjectResolver,
        mock_processor: GRPCServerMockProcessor,
        server_config: ServerConfig,
    ):
        self._obj_resolver = object_resolver
        self._mock_processor = mock_processor
        self._server_config = server_config

    @property
    def server_config(self) -> ServerConfig:
        return self._server_config

    @server_config.setter
    def server_config(self, server_config: ServerConfig):
        self._server_config = server_config

    @property
    def mock_processor(self) -> GRPCServerMockProcessor:
        return self._mock_processor

    @mock_processor.setter
    def mock_processor(self, mock_processor: GRPCServerMockProcessor):
        self._mock_processor = mock_processor

    def _create_servicer_object(
        self, parent_class: type, service_data: ServiceData,
    ) -> type | None:
        class_methods = {}

        for method_name, method_data in service_data.methods.items():
            class_methods[
                method_name
            ] = self._mock_processor.generate_method_processor(
                service_data,
                method_data,
            )

        return type(
            self.CUSTOM_SERVICER_FORMAT.format(service_data.name),
            (parent_class,),
            class_methods,
        )()

    def build_server(
        self,
        config_file_dir: str,
        interceptors: [ServerInterceptor],
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> Server:
        resolver = self._obj_resolver
        server = grpc.aio.server(
            interceptors=interceptors
        )

        for socket_data in self.server_config.sockets:
            if socket_data.certificates is None:
                server.add_insecure_port(socket_data.socket)
            else:
                cert_config = socket_data.certificates
                cert_data = read_file(get_path_relative_to_config(
                    config_file_dir, cert_config.certificate,
                ))
                key_data = read_file(get_path_relative_to_config(
                    config_file_dir, cert_config.certificate,
                ))
                root_cert_data = None
                if cert_config.root_certificate is not None:
                    root_cert_data = read_file(get_path_relative_to_config(
                        config_file_dir, cert_config.root_certificate,
                    ))
                credentials = grpc.ssl_server_credentials(
                    [(key_data, cert_data)],
                    root_cert_data,
                    root_cert_data is not None,
                )
                server.add_secure_port(socket_data.socket, credentials)

        for service_data in resolver.summarized_structure.services.values():
            servicer = self._create_servicer_object(
                resolver.get_servicer_type(service_data),
                service_data,
            )
            function = resolver.get_servicer_function(service_data)
            if servicer is None or function is None:
                continue
            function(servicer, server)

        if self.server_config.reflection_enabled:
            reflection_services = [
                reflection.SERVICE_NAME,
                *resolver.summarized_structure.services.keys(),
            ]
            reflection.enable_server_reflection(reflection_services, server)

        if loop is not None:
            server._loop = loop

        return server
