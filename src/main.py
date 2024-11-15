import asyncio
import logging
import logging.config
import os
import sys
from argparse import Namespace, ArgumentParser
from signal import SIGINT, SIGTERM

import yaml
from grpc.aio import Server

from logs import configure_all, LoggerConfig
from server.proxy import ProxyProcessor
from utils import (
    get_exception_error, get_path_relative_to_config, read_file_bytes
)
from protobuf.compilers import GRPCSourceGenerator, GRPCCompiler
from model.config import parse_config, ServerConfig
from protobuf.definitions import ProtoFilesPaths
from server.configurers import GoogleGRPCServerConfigurer
from server.processors import GRPCServerMockProcessor, APILogProcessor
from server.helpers import ProtoObjectResolver

logger = logging.getLogger(__name__)


def set_default_logging_config():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    configure_all(logging.INFO, False, [handler])


def get_proto_files_paths(
    server_config: ServerConfig, config_file_dir: str,
) -> ProtoFilesPaths:
    if isinstance(server_config.proto_files, str):
        file_paths = [server_config.proto_files]
    else:
        file_paths = server_config.proto_files
    base_dir_path = server_config.proto_files_base_dir
    result_file_paths = []

    for file_path in file_paths:
        result_file_paths.append(get_path_relative_to_config(
            config_file_dir, file_path,
        ))

    if not base_dir_path:
        base_dir_path = os.path.dirname(os.path.commonprefix(result_file_paths))
    elif not os.path.isabs(base_dir_path):
        base_dir_path = os.path.normpath(
            os.path.join(os.path.abspath(config_file_dir), base_dir_path)
        )

    return ProtoFilesPaths(
        base_dir_abs=base_dir_path,
        proto_files_abs=result_file_paths,
    )


def create_server(
    server_config: ServerConfig,
    config_file_dir: str,
    loop: asyncio.AbstractEventLoop,
    api_loggers_config: LoggerConfig,
) -> tuple[Server, GoogleGRPCServerConfigurer]:
    proto_paths = get_proto_files_paths(server_config, config_file_dir)

    g = GRPCSourceGenerator(proto_paths)
    generated_data = g.generate_source_files()

    c = GRPCCompiler(proto_paths, generated_data)

    grpc_modules = c.execute_files()

    logger.debug("Proto files parsing successful")

    object_resolver = ProtoObjectResolver(
        generated_data,
        grpc_modules,
        c.proto_structure,
    )
    log_processor = APILogProcessor(api_loggers_config)
    api_log_interceptors = []

    configurer = GoogleGRPCServerConfigurer(
        object_resolver,
        GRPCServerMockProcessor(
            object_resolver, server_config, log_processor,
            ProxyProcessor(object_resolver),
        ),
        server_config,
    )
    server = configurer.build_server(
        config_file_dir, api_log_interceptors, loop
    )
    return server, configurer


def init_arguments() -> Namespace:
    arg_parser = ArgumentParser(
        prog="cap-grpc",
        description="gRPC API mocking tool")
    arg_parser.add_argument(
        "-c",
        default="cap-grpc.yml",
        metavar="config",
        type=str,
        help="configuration .yml file path")
    return arg_parser.parse_args()


def parse_from_yaml(value: bytes) -> dict:
    try:
        return yaml.safe_load(value)
    except Exception as e:
        raise IOError(
            "YAML parsing error. " + get_exception_error(e)
        )


def configure_uvicorn_logging():
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.disabled = True


async def stop_grpc_server(
    server_data: tuple[Server, GoogleGRPCServerConfigurer]
):
    await server_data[0].stop(grace=None)

    server_config = server_data[1].server_config
    alias = ""
    if server_config.alias is not None:
        alias = f"'{server_config.alias}'"
    sockets_str = ", ".join([v.socket for v in server_config.sockets])
    logger.info(f"Stopped {alias} gRPC server on {sockets_str}")


async def start_grpc_server(
    server_data: tuple[Server, GoogleGRPCServerConfigurer]
):
    await server_data[0].start()

    server_config = server_data[1].server_config
    alias = ""
    if server_config.alias is not None:
        alias = f"'{server_config.alias}'"
    sockets_str = ", ".join([v.socket for v in server_config.sockets])
    logger.info(f"Started {alias} gRPC server on {sockets_str}")


async def start_grpc_servers(
    servers: list[tuple[Server, GoogleGRPCServerConfigurer]],
):
    await asyncio.gather(
        *[start_grpc_server(server_data) for server_data in servers]
    )
    logger.info("All servers started")


async def shutdown_grpc_servers(
    servers: list[tuple[Server, GoogleGRPCServerConfigurer]],
):
    await asyncio.gather(
        *[stop_grpc_server(server_data) for server_data in servers]
    )
    logger.info("All servers stopped")

    close_resources_functions = []
    for server_data in servers:
        close_resources_functions.append(
            server_data[1].mock_processor.proxy_processor.close_channels()
        )
    await asyncio.gather(*close_resources_functions)



async def wait_for_servers_termination(
    servers: list[tuple[Server, GoogleGRPCServerConfigurer]],
):
    await asyncio.gather(
        *[server_data[0].wait_for_termination() for server_data in servers]
    )


async def run_servers(
    servers: list[tuple[Server, GoogleGRPCServerConfigurer]]
):
    await start_grpc_servers(servers)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def handle_shutdown_signal():
        loop.create_task(shutdown_grpc_servers(servers))
        stop_event.set()

    loop.add_signal_handler(SIGINT, handle_shutdown_signal)
    loop.add_signal_handler(SIGTERM, handle_shutdown_signal)

    await stop_event.wait()
    await wait_for_servers_termination(servers)


def main():
    try:
        set_default_logging_config()

        args = init_arguments()

        config = parse_config(
            parse_from_yaml(read_file_bytes(args.c))
        )
        config_file_dir = os.path.dirname(args.c)

        configure_all(
            **config.general_logging_config.get_loggers_config().model_dump()
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        servers_data = []
        for server_config in config.servers:
            server_data = create_server(
                server_config,
                config_file_dir,
                loop,
                config.api_logging_config.get_loggers_config(),
            )
            servers_data.append(server_data)

        loop.run_until_complete(run_servers(servers_data))
    except SystemExit:
        pass
    except KeyboardInterrupt:
        logger.critical("Interrupted")
    except Exception as e:
        logger.critical(get_exception_error(e))


if __name__ == "__main__":
    main()
