import copy
import json
import logging
from typing import Any, Callable

from google.protobuf.json_format import MessageToDict
from grpc import StatusCode
from grpc._cython.cygrpc import AbortError
from grpc.aio import ServicerContext

from logs import (
    LoggerConfig, get_logger_name, REQUESTS_MOCK_LOG_PREFIX, configure_logger
)
from server.helpers import ProtoObjectResolver, get_grpc_status_code
from model.config import ServerConfig, ResponseMockConfig
from protobuf.types import GRPCType, GRPC_PYTHON_TYPES, SimpleProtoType
from protobuf.definitions import (
    MessageProperty, PropertyLabel, ServiceData, MethodData
)
from server.proxy import ProxyProcessor
from utils import get_exception_error

logger = logging.getLogger(__name__)


def merge_response_values(
    initial: dict | None, merged: dict | None
) -> dict | None:
    if initial is None or merged is None:
        return initial or merged

    result = copy.deepcopy(initial)
    for k, merged_v in merged.items():
        if k in result:
            result_v = result[k]
            if type(merged_v) == type(result_v):
                if isinstance(merged_v, dict):
                    result[k] = merge_response_values(result_v, merged_v)
        else:
            result[k] = merged_v
    return result


class APILogProcessor:
    def __init__(self, loggers_conf: LoggerConfig):
        self._loggers_conf = loggers_conf
        self._loggers = {}

    def get_requests_logger(
        self,
        service_data: ServiceData,
        method_data: MethodData,
    ) -> logging.Logger:
        logger_name = get_logger_name([
            REQUESTS_MOCK_LOG_PREFIX, service_data.full_name, method_data.name
        ])
        logger = self._loggers.get(logger_name)
        if logger is None:
            logger = logging.getLogger(logger_name)
            configure_logger(logger, **self._loggers_conf.model_dump())
            self._loggers[logger_name] = logger
        return logger

    def log_request_data(
        self,
        request_object: object,
        context: ServicerContext,
        server_config: ServerConfig,
        service_data: ServiceData,
        method_data: MethodData,
    ):
        api_logger = self.get_requests_logger(service_data, method_data)
        request_dict = MessageToDict(request_object)

        extra = {
            "service": service_data.full_name,
            "method": method_data.name,
            "request_message": json.dumps(request_dict),
            "sockets": ", ".join([
                socket_data.socket for socket_data in server_config.sockets
            ])
        }

        if server_config.alias is not None:
            extra["alias"] = server_config.alias
        metadata_dict = {}
        metadata = context.invocation_metadata()
        if metadata is not None:
            for k, v in metadata:
                if k in metadata_dict:
                    if isinstance(metadata_dict[k], list):
                        metadata_dict[k].append(v)
                    else:
                        metadata_dict[k] = [metadata_dict[k], v]
                else:
                    metadata_dict[k] = v
        if metadata_dict:
            extra["metadata"] = metadata_dict

        api_logger.info("Input message", extra=extra)


    def log_response_data(
        self,
        response_object: object | None,
        context: ServicerContext,
        server_config: ServerConfig,
        service_data: ServiceData,
        method_data: MethodData,
    ):
        api_logger = self.get_requests_logger(service_data, method_data)

        extra = {
            "service": service_data.full_name,
            "method": method_data.name,
            "sockets": ", ".join([
                socket_data.socket for socket_data in server_config.sockets
            ])
        }

        if server_config.alias is not None:
            extra["alias"] = server_config.alias
        response_dict = None
        if response_object is not None:
            response_dict = MessageToDict(response_object)
        if response_dict is not None:
            extra["response_message"] = json.dumps(response_dict)
        error_details = context.details()
        if error_details:
            extra["error_details"] = error_details
        code = context.code()
        if code is not None:
            code: StatusCode
            extra["code"] = f"{code.value[0]}: {code.value[1]}"
        metadata_dict = {}
        metadata = context.trailing_metadata()
        if metadata is not None:
            for metadata_item in metadata:
                key = metadata_item[0]
                value = metadata_item[1]
                if key in metadata_dict:
                    if isinstance(metadata_dict[key], list):
                        metadata_dict[key].append(value)
                    else:
                        metadata_dict[key] = [metadata_dict[key], value]
                else:
                    metadata_dict[key] = value
        if metadata_dict:
            extra["metadata"] = metadata_dict

        api_logger.info("Output message", extra=extra)


class GRPCServerMockProcessor:
    def __init__(
        self,
        object_resolver: ProtoObjectResolver,
        server_config: ServerConfig,
        log_processor: APILogProcessor,
        proxy_processor: ProxyProcessor,
    ):
        self._object_resolver = object_resolver
        self._server_config = server_config
        self._log_processor = log_processor
        self._proxy_processor = proxy_processor

    @property
    def proxy_processor(self) -> ProxyProcessor:
        return self._proxy_processor

    def get_enum_value(
        self,
        enum_name: str,
        value: str | None = None,
    ) -> object | None:
        enum_data = self._object_resolver.summarized_structure.enums[
            enum_name
        ]
        if enum_data is None:
            return None
        enum_type = self._object_resolver.get_enum_type(enum_data)
        if enum_type is None:
            return None
        for enum_property in enum_data.properties:
            if value is None:
                return enum_type.Value(enum_property.name)
            elif value == enum_property.name:
                return enum_type.Value(enum_property.name)
        return None

    def get_simple_value(self, grpc_type: GRPCType, value: Any):
        type_data = GRPC_PYTHON_TYPES[grpc_type]
        result = type_data.default_value
        if value is not None:
            if type(value) is type_data.python_type or isinstance(
                value, SimpleProtoType
            ):
                try:
                    result = type_data.converter(value)
                except:
                    pass
        return result

    def fill_object(self, property_data: MessageProperty, value: Any) -> dict:
        if property_data.label == property_data.label.OPTIONAL and value is None:
            return {}
        else:
            return {property_data.name: value}

    def repeat_if_required(
        self,
        property_data: MessageProperty,
        mock_value: Any,
        inner_message_function: Callable,
        *args,
    ) -> list[Any]:
        if property_data.label == PropertyLabel.REPEATED:
            values = []
            mocks_list = mock_value
            if not isinstance(mocks_list, list):
                mocks_list = [mocks_list]
            for mock_data in mocks_list:
                values.append(inner_message_function(
                    *args, mock_data
                ))
            return values
        else:
            return inner_message_function(
                *args, mock_value
            )

    def get_message_value(
        self,
        message_name: str,
        mock_value: Any,
    ) -> object:
        response_dict = {}
        if not isinstance(mock_value, dict):
            mock_value = None

        out_data = self._object_resolver.summarized_structure.messages[
            message_name
        ]
        response_type = self._object_resolver.get_message_type(out_data)

        for property_data in out_data.properties:
            mock_property_value = None
            if mock_value is not None:
                mock_property_value = mock_value.get(property_data.name)

            if property_data.grpc_type == GRPCType.MESSAGE:
                property_value = self.repeat_if_required(
                    property_data,
                    mock_property_value,
                    self.get_message_value,
                    property_data.nested_message,
                )
            elif property_data.grpc_type == GRPCType.ENUM:
                property_value = self.repeat_if_required(
                    property_data,
                    mock_property_value,
                    self.get_enum_value,
                    property_data.nested_enum,
                )
            elif property_data.grpc_type == GRPCType.GROUP:
                property_value = None # For future versions
            else:
                property_value = self.repeat_if_required(
                    property_data,
                    mock_property_value,
                    self.get_simple_value,
                    property_data.grpc_type,
                )
            response_dict.update(self.fill_object(
                property_data, property_value
            ))
        response = response_type(**response_dict)
        return response

    async def set_error_data(
        self,
        context: ServicerContext,
        mock_data: ResponseMockConfig | None,
    ):
        if mock_data is None:
            return
        if mock_data.error is None:
            return

        await context.abort(
            get_grpc_status_code(mock_data.error.code),
            mock_data.error.details,
        )

    def set_trailing_metadata(
        self,
        context: ServicerContext,
        mock_data: ResponseMockConfig | None,
    ):
        if mock_data is None:
            return
        if not mock_data.metadata:
            return
        metadata_list = []
        for key, value in mock_data.metadata.items():
            if isinstance(value, list):
                for value_item in value:
                    metadata_list.append((key, value_item))
            else:
                metadata_list.append((key, value))
        context.set_trailing_metadata(metadata_list)

    async def process_request_proxying(
        self,
        request: object,
        context: ServicerContext,
    ) -> object:
        pass

    def generate_method_processor(
        self,
        service_data: ServiceData,
        method_data: MethodData,
    ) -> Callable | None:
        mock_data = None
        service_key = service_data.full_name

        if self._server_config.mocks is not None:
            mock_data = self._server_config.mocks.root.get(
                service_key, {}
            ).get(method_data.name)
        default_response_func = self.get_message_value
        metadata_function = self.set_trailing_metadata
        log_processor = self._log_processor
        error_function = self.set_error_data
        proxy_func = self._proxy_processor.process_request_proxying
        server_config = self._server_config

        async def processor_func(
            self, request: object, context: ServicerContext
        ) -> object:
            response = None
            mock_value = None
            if mock_data is not None:
                mock_value = mock_data.value

            log_processor.log_request_data(
                request,
                context,
                server_config,
                service_data,
                method_data,
            )
            try:
                if mock_data and mock_data.proxy:
                    proxy_res_value = await proxy_func(
                        request,
                        context,
                        service_data,
                        method_data,
                        mock_data.proxy,
                    )
                    mock_value = merge_response_values(
                        proxy_res_value, mock_value
                    )

                metadata_function(context, mock_data)
                await error_function(context, mock_data)
                response = default_response_func(
                    method_data.output_param.message, mock_value,
                )
            except AbortError:
                raise
            except Exception as e:
                logger.error(get_exception_error(e))
                await context.abort(
                    StatusCode.UNKNOWN,
                    "Mock API server internal error"
                )
            finally:
                log_processor.log_response_data(
                    response,
                    context,
                    server_config,
                    service_data,
                    method_data,
                )
            return response

        return processor_func
