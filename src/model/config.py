import logging
import sys
from enum import Enum
from textwrap import dedent
from typing import Optional, List, Dict, Any, Annotated

from grpc import StatusCode
from pydantic import BaseModel, Field, ValidationError, RootModel, AfterValidator

from logs import LoggerConfig
from logs.formatters import YamlFormatter
from utils import get_exception_error
from model.validators import (
    get_validation_error_message,
    validate_grpc_meta_key,
    validate_grpc_meta_value,
    validate_grpc_error_status_code
)


MetadataKey = Annotated[str, AfterValidator(validate_grpc_meta_key)]
MetadataValue = Annotated[str, AfterValidator(validate_grpc_meta_value)]
GRPCErrorCode = Annotated[int, AfterValidator(
    validate_grpc_error_status_code
)]


class ErrorConfig(BaseModel):
    code: GRPCErrorCode = Field(
        StatusCode.UNKNOWN.value[0],
        description="Error response status code"
    )
    details: str = Field(
        "",
        description="Error response message"
    )


class ProxyConfig(BaseModel):
    socket: str = Field(
        None,
        description="gRPC server socket for proxying requests"
    )
    seconds_timeout: float | None = Field(
        None,
        description="gRPC server proxying timeout",
        ge=0,
    )


class ResponseMockConfig(BaseModel):
    value: Dict[str, Any] | None = Field(
        None,
        description="Response message value"
    )
    metadata: dict[MetadataKey, MetadataValue] = Field(
        {},
        description="Response metadata value"
    )
    error: ErrorConfig | None = Field(
        None,
        description="Error data for mocking errors"
    )
    proxy: ProxyConfig | None = Field(
        None,
        description="Requests proxying configuration"
    )


class GrpcMockData(RootModel):
    root: Dict[str, Dict[str, ResponseMockConfig]]


class CertificatesConfig(BaseModel):
    certificate: str = Field(
        ...,
        description="gRPC server socket certificate"
    )
    key_file: str = Field(
        ...,
        description="gRPC server socket key file"
    )
    root_certificate: str | None = Field(
        None,
        description="Root CA certificate for validation client certificates"
    )


class SocketsConfig(BaseModel):
    socket: str = Field(
        ...,
        description="gRPC server socket"
    )
    certificates: CertificatesConfig | None = Field(
        None,
        description="Enables secure and encrypted connection with "
                    "certificates on socket"
    )


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


class LoggingConfig(BaseModel):
    console: bool = Field(
        ...,
        description="Whether to log messages to console",
    )
    files: list[str] = Field(
        [],
        description="Files to print logs messages into",
    )
    level: LoggingLevel = Field(
        LoggingLevel.INFO,
        description="Logging level",
    )
    format: LoggingFormat = Field(
        LoggingFormat.TEXT,
        description="Type of logs records",
    )
    format_line: str = Field(
        "%(message)s",
        description="Formatter pattern",
    )

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


class ServerConfig(BaseModel):
    alias: Optional[str] = Field(
        None,
        description="Server alias"
    )
    sockets: list[SocketsConfig] = Field(
        ...,
        description="gRPC server sockets list",
        min_length=1,
    )
    reflection_enabled: bool = Field(
        True,
        description="Whether the reflection should enabled on GRPC server"
    )
    proto_files: list[str] | str = Field(
        ...,
        description=".proto file/files paths or pattern"
    )
    proto_files_base_dir: str | None = Field(
        None,
        description=dedent(
            "Base directory path for all proto files compilation"
        )
    )
    mocks: GrpcMockData | None = Field(
        None,
        description="Server mocks data"
    )


class Config(BaseModel):
    servers: List[ServerConfig] = Field(
        ...,
        description="Servers list",
        min_length=1,
    )
    general_logging_config: LoggingConfig = Field(
        LoggingConfig(
            console=True,
            level=LoggingLevel.INFO,
            format=LoggingFormat.TEXT,
            format_line="%(levelname)s: %(message)s",
        ),
        description="Logging configuration"
    )
    api_logging_config: LoggingConfig = Field(
        LoggingConfig(
            console=True,
            level=LoggingLevel.INFO,
            format=LoggingFormat.YAML,
            format_line="%(request_message)s %(response_message)s "
                        "%(method)s %(service)s %(code)s %(error_details)s"
                        "%(metadata)s %(alias)s",
        ),
        description="Logging configuration"
    )


def parse_config(raw_config: dict) -> Config:
    try:
        config = Config.model_validate(raw_config)
        return config
    except ValidationError as e:
        raise IOError(
            "Config file parsing error. " +
            get_validation_error_message(e)
        )
    except ValueError as e:
        raise IOError(
            "Config file parsing error. " +
            get_exception_error(e)
        )
