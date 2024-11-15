import asyncio
import logging

from google.protobuf.json_format import MessageToDict
from grpc import ServicerContext
from grpc.aio import AioRpcError, insecure_channel

from model.config import ProxyConfig
from protobuf.definitions import ServiceData, MethodData
from server.helpers import ProtoObjectResolver
from utils import get_exception_error

logger = logging.getLogger(__name__)


class ProxyProcessor:
    def __init__(
        self,
        object_resolver: ProtoObjectResolver,
    ):
        self._object_resolver = object_resolver
        self._channels_dict = {}

    async def process_request_proxying(
        self,
        request: object,
        context: ServicerContext,
        service_data: ServiceData,
        method_data: MethodData,
        proxy_config: ProxyConfig,
    ) -> dict | None:
        try:
            stub_type = self._object_resolver.get_stub_type(service_data)
            if stub_type is None:
                logger.error("Proxying request internal error")

                return None
            if proxy_config not in self._channels_dict:
                channel = insecure_channel(proxy_config.socket)
                self._channels_dict[proxy_config.socket] = channel
            else:
                channel = self._channels_dict[proxy_config.socket]
            stub = stub_type(channel)
            method_func = getattr(stub, method_data.name, None)

            metadata_list = []
            metadata = context.invocation_metadata()
            if metadata is not None:
                for k, v in metadata:
                    metadata_list.append((k, v))

            response = await method_func(
                request, metadata=metadata_list
            )
            if response is None:
                logger.error("Proxying request internal error")

                return None
            return MessageToDict(response)
        except AioRpcError as e:
            context.set_trailing_metadata(e.trailing_metadata())
            await context.abort(
                e.code(),
                e.details(),
            )
        except Exception as e:
            logger.error(
                f"Proxying request internal error. {get_exception_error(e)}"
            )

    async def close_channels(self):
        await asyncio.gather(
            *[channel.close() for channel in self._channels_dict.values()]
        )
