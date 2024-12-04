import logging
import sys
from enum import Enum
from typing import Any, Annotated

from grpc import StatusCode
from pydantic import (
    BaseModel, RootModel, AfterValidator, ConfigDict
)

from logs import LoggerConfig
from logs.formatters import YamlFormatter
import config.validators as v


MetadataKey = Annotated[str, AfterValidator(v.validate_grpc_meta_key)]
MetadataValue = Annotated[str, AfterValidator(v.validate_grpc_meta_value)]
GRPCErrorCode = Annotated[int, AfterValidator(
    v.validate_grpc_error_status_code
)]
FormatLine = Annotated[str, AfterValidator(v.validate_logging_keys)]


class BaseConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorConfig(BaseConfigModel):
    code: GRPCErrorCode | str = StatusCode.UNKNOWN.value[0]
    details: str = ""


class ProxyConfig(BaseConfigModel):
    socket: str
    seconds_timeout: float | str | None = None


class ResponseMockConfig(BaseConfigModel):
    messages: dict[str, Any] | list[dict[str, Any]] | str = {}
    trailing_meta: str | dict[MetadataKey, MetadataValue] = {}
    error: ErrorConfig | None = None
    seconds_delay: str | float | None = None
    proxy: ProxyConfig | None = None


class GrpcMockData(RootModel):
    root: dict[str, dict[str, ResponseMockConfig | str | None]]


class CertificatesConfig(BaseConfigModel):
    certificate: str
    key_file: str
    root_certificate: str | None = None


class SocketsConfig(BaseConfigModel):
    socket: str
    certificates: CertificatesConfig | None = None


class LoggingLevel(str, Enum):
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"

    def to_int_value(self) -> int:
        if self is LoggingLevel.CRITICAL:
            return logging.CRITICAL
        elif self is LoggingLevel.FATAL:
            return logging.FATAL
        elif self is LoggingLevel.ERROR:
            return logging.ERROR
        elif self is LoggingLevel.WARNING:
            return logging.WARNING
        elif self is LoggingLevel.INFO:
            return logging.INFO
        elif self is LoggingLevel.DEBUG:
            return logging.DEBUG
        else:
            return logging.FATAL


class LoggingFormat(str, Enum):
    TEXT = "text"
    YAML = "yaml"


class LoggingConfig(BaseConfigModel):
    console: bool
    files: list[str] = []
    level: LoggingLevel = LoggingLevel.INFO
    format: LoggingFormat = LoggingFormat.TEXT
    format_line: FormatLine = "%(message)s"

    def get_loggers_config(self) -> LoggerConfig:
        if self.format == LoggingFormat.TEXT:
            formatter = logging.Formatter(self.format_line)
        else:
            formatter = YamlFormatter(self.format_line)
        handlers = []
        if self.console:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            handlers.append(handler)
        for filepath in self.files:
            handler = logging.FileHandler(filepath)
            handler.setFormatter(formatter)
            handlers.append(handler)
        return LoggerConfig(
            level=self.level.to_int_value(),
            disabled=not handlers,
            handlers=handlers,
        )


class ServerConfig(BaseConfigModel):
    alias: str
    sockets: list[SocketsConfig]
    reflection_enabled: bool = True
    proto_files: list[str] | str
    proto_files_base_dir: str | None = None
    mocks: GrpcMockData | None = None


class Config(BaseConfigModel):
    servers: list[ServerConfig]
    general_logging_config: LoggingConfig = LoggingConfig(
        console=True,
        level=LoggingLevel.INFO,
        format=LoggingFormat.TEXT,
        format_line="%(levelname)s: %(message)s",
    )
    api_logging_config: LoggingConfig = LoggingConfig(
        console=True,
        level=LoggingLevel.INFO,
        format=LoggingFormat.YAML,
        format_line="%(message)s, (request_message)s %(response_message)s "
                    "%(method)s %(service)s %(code)s %(error_details)s"
                    "%(metadata)s %(alias)s %(timestamp)s",
    )
