import json
from logging import Logger, getLogger

from grpc import StatusCode
from grpc.aio import ServicerContext

from logs import (
    get_logger_name, REQUESTS_MOCK_LOG_PREFIX, configure_logger, LoggerConfig
)
from protobuf.definitions import ServiceData, MethodData
from server.processors.base import ProcessingMeta, extract_invocation_metadata


class APILogProcessor:
    def __init__(self, loggers_conf: LoggerConfig):
        self._loggers_conf = loggers_conf
        self._loggers = {}

    def get_requests_logger(
        self,
        service_data: ServiceData,
        method_data: MethodData,
    ) -> Logger:
        logger_name = get_logger_name([
            REQUESTS_MOCK_LOG_PREFIX, service_data.full_name, method_data.name
        ])
        logger_obj = self._loggers.get(logger_name)
        if logger_obj is None:
            logger_obj = getLogger(logger_name)
            configure_logger(logger_obj, **self._loggers_conf.model_dump())
            self._loggers[logger_name] = logger_obj
        return logger_obj

    def log_req_message(
        self,
        request_dict: dict,
        meta: ProcessingMeta,
    ):
        api_logger = self.get_requests_logger(
            meta.service_data, meta.method_data
        )

        extra = {
            "service": meta.service_data.full_name,
            "method": meta.method_data.name,
            "request_message": json.dumps(request_dict),
            "alias": meta.server_config.alias,
        }

        api_logger.info("Input message", extra=extra)

    def log_req_initial_meta(
        self,
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        api_logger = self.get_requests_logger(
            meta.service_data, meta.method_data
        )

        metadata_dict = extract_invocation_metadata(context)
        if metadata_dict:
            extra = {
                "service": meta.service_data.full_name,
                "method": meta.method_data.name,
                "alias": meta.server_config.alias,
                "metadata": metadata_dict
            }
            if meta.server_config.alias is not None:
                extra["alias"] = meta.server_config.alias

            api_logger.info("Invocation metadata", extra=extra)

    def log_res_message(
        self,
        response_dict: dict,
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        api_logger = self.get_requests_logger(
            meta.service_data, meta.method_data
        )

        extra = {
            "service": meta.service_data.full_name,
            "method": meta.method_data.name,
            "alias": meta.server_config.alias,
        }

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

    def log_res_error(
        self,
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        api_logger = self.get_requests_logger(
            meta.service_data, meta.method_data,
        )

        extra = {
            "service": meta.service_data.full_name,
            "method": meta.method_data.name,
            "alias": meta.server_config.alias,
        }

        error_details = context.details()
        if error_details:
            extra["error_details"] = error_details
        code = context.code()
        if code is not None:
            code: StatusCode
            extra["code"] = f"{code.value[0]}: {code.value[1]}"

        api_logger.info("Output error", extra=extra)

    def log_res_trailing_meta(
        self,
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        api_logger = self.get_requests_logger(
            meta.service_data, meta.method_data
        )

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
            extra = {
                "service": meta.service_data.full_name,
                "method": meta.method_data.name,
                "alias": meta.server_config.alias,
                "metadata": metadata_dict
            }
            api_logger.info("Trailing metadata", extra=extra)
