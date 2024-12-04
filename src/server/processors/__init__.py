import logging
from asyncio import sleep
from typing import Callable, AsyncIterator

from google.protobuf.json_format import MessageToDict
from grpc import StatusCode
from grpc._cython.cygrpc import AbortError
from grpc.aio import ServicerContext

from config.model import ServerConfig, ResponseMockConfig
from protobuf.definitions import ServiceData, MethodData
from server.helpers import ProtoObjectResolver
from server.processors.base import ProcessingMeta
from server.processors.logs import APILogProcessor
from server.processors.proxy import ProxyProcessor
from server.processors.templates import TemplateProcessor
from utils import get_exception_error
import server.processors.mock as mocks

logger = logging.getLogger(__name__)


class ResponseProcessor:
    def __init__(
        self,
        object_resolver: ProtoObjectResolver,
        server_config: ServerConfig,
        template_processor: TemplateProcessor,
        log_processor: APILogProcessor,
        proxy_processor: ProxyProcessor,
    ):
        self._object_resolver = object_resolver
        self._server_config = server_config
        self._log_processor = log_processor
        self._proxy_processor = proxy_processor
        self._template_processor = template_processor

    def generate_method_processor(
        self,
        service_data: ServiceData,
        method_data: MethodData,
    ) -> Callable | None:
        if method_data.output_message.streaming:
            mock_config = ResponseMockConfig(messages=[])
        else:
            mock_config = ResponseMockConfig(messages={})
        service_key = service_data.full_name

        if self._server_config.mocks is not None:
            retrieved = self._server_config.mocks.root.get(
                service_key, {}
            ).get(method_data.name)
            if retrieved is not None:
                mock_config = retrieved

        mock_data_func = self._template_processor.create_mock_data
        message_func = mocks.get_service_message
        metadata_func = mocks.set_trailing_metadata
        error_function = mocks.set_error_data
        log_in_message_func = self._log_processor.log_req_message
        log_out_message_func = self._log_processor.log_res_message
        log_initial_meta_func = self._log_processor.log_req_initial_meta
        log_trailers_func = self._log_processor.log_res_trailing_meta
        log_error_func = self._log_processor.log_res_error
        get_proxy = self._proxy_processor.get_proxy_function

        meta = ProcessingMeta(
            object_resolver=self._object_resolver,
            server_config=self._server_config,
            service_data=service_data,
            method_data=method_data,
            mock_config=mock_config,
        )

        async def process_request(
            input_data: object, context: ServicerContext
        ) -> tuple[list[dict], list[object]]:
            request_dicts, requests = [], []
            log_initial_meta_func(context, meta)
            if isinstance(input_data, AsyncIterator):
                async for request in input_data:
                    request_dict = message_func(
                        meta,
                        meta.method_data.input_message.name,
                        MessageToDict(request),
                    )[0]
                    log_in_message_func(request_dict, meta)
                    requests.append(request)
                    request_dicts.append(request_dict)
            else:
                request_dict = message_func(
                    meta,
                    meta.method_data.input_message.name,
                    MessageToDict(input_data),
                )[0]
                log_in_message_func(request_dict, meta)
                requests.append(input_data)
                request_dicts.append(request_dict)

            await mock_data_func(request_dicts, context, meta)
            seconds_delay = meta.mock_data.seconds_delay
            if seconds_delay is not None:
                logger.debug(f"'{seconds_delay}' seconds delay for request")
                await sleep(seconds_delay)

            return request_dicts, requests

        async def process_unary_response(
            input: object, context: ServicerContext
        ) -> object:
            try:
                request_dicts, requests = await process_request(input, context)
                proxy_func = get_proxy(meta)
                if proxy_func:
                    response_dict = await proxy_func(requests, context, meta)
                else:
                    response_dict = meta.mock_data.messages.root
                    if isinstance(meta.mock_data.messages.root, list):
                        if len(meta.mock_data.messages.root) > 0:
                            response_dict = meta.mock_data.messages.root[0]
                metadata_func(context, meta)
                await error_function(context, meta)
                response_dict, response = message_func(
                    meta,
                    meta.method_data.output_message.name,
                    response_dict,
                )
                log_out_message_func(response_dict, context, meta)
                return response
            except AbortError:
                log_trailers_func(context, meta)
                log_error_func(context, meta)
                raise
            except Exception as e:
                logger.error(get_exception_error(e))
                log_trailers_func(context, meta)
                log_error_func(context, meta)
                await context.abort(
                    StatusCode.UNKNOWN,
                    "Mock API server internal error",
                )

        async def process_stream_response(
            input: object, context: ServicerContext
        ) -> object:
            try:
                request_dicts, requests = await process_request(input, context)
                proxy_func = get_proxy(meta)
                await error_function(context, meta)
                if proxy_func:
                    async for response_dict in proxy_func(
                        requests, context, meta
                    ):
                        response_dict, response = message_func(
                            meta,
                            meta.method_data.output_message.name,
                            response_dict,
                        )
                        log_out_message_func(response_dict, context, meta)
                        yield response
                else:
                    if isinstance(meta.mock_data.messages.root, list):
                        for response_dict in meta.mock_data.messages.root:
                            response_dict, response = message_func(
                                meta,
                                meta.method_data.output_message.name,
                                response_dict,
                            )
                            log_out_message_func(response_dict, context, meta)
                            yield response
                    else:
                        response_dict, response = message_func(
                            meta,
                            meta.method_data.output_message.name,
                            meta.mock_data.messages.root,
                        )
                        log_out_message_func(response_dict, context, meta)
                        yield response
                await error_function(context, meta)
                metadata_func(context, meta)
            except AbortError:
                log_trailers_func(context, meta)
                log_error_func(context, meta)
                raise
            except Exception as e:
                code = StatusCode.UNKNOWN
                message = "Mock API server internal error"

                logger.error(get_exception_error(e))
                log_trailers_func(context, meta)
                context.set_code(code)
                context.set_details(message)
                log_error_func(context, meta)
                await context.abort(code, message)
            log_trailers_func(context, meta)

        if method_data.output_message.streaming:
            return process_stream_response
        else:
            return process_unary_response

    async def clean_resources(self):
        await self._proxy_processor.close_channels()
