from typing import Any

from grpc import StatusCode, ServicerContext
from pydantic import BaseModel, ConfigDict, Field, RootModel

from config.model import (
    ServerConfig, ResponseMockConfig, MetadataKey, MetadataValue, GRPCErrorCode
)
from protobuf.definitions import ServiceData, MethodData
from server.helpers import ProtoObjectResolver


class MessageMock(RootModel):
    root: dict[str, Any] | list[dict[str, Any]] = {}


class MetadataMock(RootModel):
    root: dict[MetadataKey, MetadataValue] = {}


class ErrorMock(BaseModel):
    code: GRPCErrorCode | str = Field(
        StatusCode.UNKNOWN.value[0],
        description="Error response status code"
    )
    details: str = Field(
        "",
        description="Error response message"
    )


class ProxyMock(BaseModel):
    socket: str = Field(
        None,
        description="gRPC server socket for proxying requests"
    )
    seconds_timeout: float | None = Field(
        None,
        description="gRPC server proxying timeout",
        ge=0,
    )


class ResponseMock(BaseModel):
    messages: MessageMock = Field(
        MessageMock(),
        description="Response message value",
    )
    trailing_meta: MetadataMock = Field(
        MetadataMock(),
        description="Initial response metadata values",
    )
    error: ErrorMock | None = Field(
        None,
        description="Error data for mocking errors",
    )
    seconds_delay: float | None = Field(
        None,
        description="Seconds delay for request processing",
        gt=0,
    )
    proxy: ProxyMock | None = Field(
        None,
        description="Requests proxying configuration",
    )


class ProcessingMeta(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    object_resolver: ProtoObjectResolver
    server_config: ServerConfig
    service_data: ServiceData
    method_data: MethodData
    mock_config: ResponseMockConfig | str
    mock_data: ResponseMock = ResponseMock()


def extract_invocation_metadata(context: ServicerContext) -> dict:
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
    return metadata_dict
