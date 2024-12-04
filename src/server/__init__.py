import logging
from asyncio import AbstractEventLoop

from grpc.aio import Server

from logs import LoggerConfig
from config.model import ServerConfig
from protobuf import get_proto_files_paths
from protobuf.compilers import StructureParser, generate_descriptor_pool
from server.configurers import GRPCServerConfigurer
from server.helpers import ProtoObjectResolver
from server.processors import (
    APILogProcessor, ResponseProcessor, TemplateProcessor
)
from server.processors.proxy import ProxyProcessor
from templates import create_base_environment

logger = logging.getLogger(__name__)


def create_server(
    server_config: ServerConfig,
    config_file_dir: str,
    loop: AbstractEventLoop,
    api_loggers_config: LoggerConfig,
) -> tuple[Server, GRPCServerConfigurer]:
    proto_paths = get_proto_files_paths(server_config, config_file_dir)

    pool = generate_descriptor_pool(proto_paths)
    structures = StructureParser(pool, proto_paths).get_structures()

    logger.debug("Proto files parsing successful")

    object_resolver = ProtoObjectResolver(structures, pool)

    configurer = GRPCServerConfigurer(
        object_resolver,
        ResponseProcessor(
            object_resolver,
            server_config,
            TemplateProcessor(create_base_environment(config_file_dir)),
            APILogProcessor(api_loggers_config),
            ProxyProcessor(),
        ),
        server_config,
    )
    server = configurer.build_server(config_file_dir, loop)

    logger.debug("Servers build successful")

    return server, configurer
