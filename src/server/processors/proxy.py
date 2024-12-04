import asyncio
import logging
from typing import Callable

from google.protobuf.json_format import MessageToDict
from grpc import ServicerContext
from grpc.aio import AioRpcError, insecure_channel

from server.processors import ProcessingMeta
from utils import get_exception_error

logger = logging.getLogger(__name__)


class ProxyProcessor:
    def __init__(self):
        self._channels_dict = {}
        self._methods_dict = {}

    def _get_proxy_methods(self, meta: ProcessingMeta) -> callable:
        proxy_config = meta.mock_config.proxy
        service_data = meta.service_data
        method_data = meta.method_data

        if proxy_config.socket not in self._channels_dict:
            channel = insecure_channel(proxy_config.socket)
            self._channels_dict[proxy_config.socket] = channel
        else:
            channel = self._channels_dict[proxy_config.socket]

        if service_data.full_name not in self._methods_dict:
            self._methods_dict[service_data.full_name] = {}
        if method_data.name not in self._methods_dict[
            service_data.full_name
        ]:
            in_type = meta.object_resolver.get_message_type(
                meta.object_resolver.summarized_structure.messages[
                    method_data.input_message.name
                ]
            )
            out_type = meta.object_resolver.get_message_type(
                meta.object_resolver.summarized_structure.messages[
                    method_data.output_message.name
                ]
            )
            if method_data.input_message.streaming:
                if method_data.output_message.streaming:
                    processor = channel.stream_stream
                else:
                    processor = channel.stream_unary
            else:
                if method_data.output_message.streaming:
                    processor = channel.unary_stream
                else:
                    processor = channel.unary_unary

            method = processor(
                f"/{service_data.full_name}/{method_data.name}",
                request_serializer=in_type.SerializeToString,
                response_deserializer=out_type.FromString,
                _registered_method=True
            )

            self._methods_dict[
                service_data.full_name
            ][method_data.name] = method
        return self._methods_dict[service_data.full_name][method_data.name]

    async def _process_unary_proxying(
        self,
        requests: list[object],
        context: ServicerContext,
        meta: ProcessingMeta,
    ) -> dict | None:
        try:
            method_func = self._get_proxy_methods(meta)

            metadata_list = []
            metadata = context.invocation_metadata()
            if metadata is not None:
                for k, v in metadata:
                    metadata_list.append((k, v))

            if meta.method_data.input_message.streaming:
                async def requests_generator():
                    for item in requests:
                        yield item
                request_obj = requests_generator
            else:
                if len(requests) == 0:
                    logger.error("Proxying request internal error")
                    return None
                request_obj = requests[0]

            timeout = None
            if meta.mock_data.proxy.seconds_timeout is not None:
                timeout = meta.mock_data.proxy.seconds_timeout

            response = await method_func(
                request_obj, metadata=metadata_list, timeout=timeout,
            )
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

    async def _process_stream_proxying(
        self,
        requests: list[object],
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        try:
            method_func = self._get_proxy_methods(meta)

            metadata_list = []
            metadata = context.invocation_metadata()
            if metadata is not None:
                for k, v in metadata:
                    metadata_list.append((k, v))

            if meta.method_data.input_message.streaming:
                request_obj = requests
            else:
                if len(requests) == 0:
                    return
                request_obj = requests[0]

            timeout = None
            if meta.mock_data.proxy.seconds_timeout is not None:
                timeout = meta.mock_data.proxy.seconds_timeout

            async for response in method_func(
                request_obj, metadata=metadata_list, timeout=timeout
            ):
                yield MessageToDict(response)
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

    def get_proxy_function(
        self, meta: ProcessingMeta
    ) -> Callable | None:
        if meta.mock_data.proxy is None:
            return None

        if meta.method_data.output_message.streaming:
            return self._process_stream_proxying
        else:
            return self._process_unary_proxying

    async def close_channels(self):
        await asyncio.gather(
            *[channel.close() for channel in self._channels_dict.values()]
        )
