from args import args
import asyncio
import logging
import os
import sys
from signal import SIGINT, SIGTERM

from grpc.aio import Server

from logs import configure_all
from server import create_server
from utils import get_exception_error, read_file_bytes, parse_from_yaml
from config import parse_config
from server.configurers import GRPCServerConfigurer

logger = logging.getLogger(__name__)


def set_default_logging_config():
    os.environ["GRPC_VERBOSITY"] = "NONE"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    configure_all(logging.INFO, False, [handler])


async def stop_grpc_server(
    server_data: tuple[Server, GRPCServerConfigurer],
):
    await server_data[0].stop(None)

    server_config = server_data[1].server_config
    alias = ""
    if server_config.alias is not None:
        alias = f"'{server_config.alias}'"
    sockets_str = ", ".join([v.socket for v in server_config.sockets])
    logger.info(f"Stopped {alias} gRPC server on {sockets_str}")


async def start_grpc_server(
    server_data: tuple[Server, GRPCServerConfigurer]
):
    await server_data[0].start()

    server_config = server_data[1].server_config
    alias = ""
    if server_config.alias is not None:
        alias = f"'{server_config.alias}'"
    sockets_str = ", ".join([v.socket for v in server_config.sockets])
    logger.info(f"Started {alias} gRPC server on {sockets_str}")


async def start_grpc_servers(
    servers: list[tuple[Server, GRPCServerConfigurer]],
):
    await asyncio.gather(
        *[start_grpc_server(server_data) for server_data in servers]
    )
    logger.info("All servers started")


async def shutdown_grpc_servers(
    servers: list[tuple[Server, GRPCServerConfigurer]]
):
    await asyncio.gather(
        *[stop_grpc_server(server_data) for server_data in servers]
    )
    logger.info("All servers stopped")

    close_resources_functions = []
    for server_data in servers:
        close_resources_functions.append(
            server_data[1].response_processor.clean_resources()
        )
    await asyncio.gather(*close_resources_functions)
    logger.debug("All resources released")


async def wait_for_servers_termination(
    servers: list[tuple[Server, GRPCServerConfigurer]],
):
    await asyncio.gather(
        *[server_data[0].wait_for_termination() for server_data in servers]
    )


async def run_servers(
    servers: list[tuple[Server, GRPCServerConfigurer]]
):
    await start_grpc_servers(servers)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def grace_shutdown():
        loop.create_task(shutdown_grpc_servers(servers))
        stop_event.set()

    loop.add_signal_handler(SIGINT, grace_shutdown)
    loop.add_signal_handler(SIGTERM, grace_shutdown)

    await stop_event.wait()
    await wait_for_servers_termination(servers)


def main():
    try:
        set_default_logging_config()

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
