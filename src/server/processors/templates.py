from logging import getLogger
from typing import TypeVar, Type, Any

from grpc import StatusCode
from grpc.aio import ServicerContext
from jinja2 import Environment
from pydantic import BaseModel, ValidationError, RootModel
from yaml import YAMLError

import constants as c
from templates import AccessibleVariable
from config.model import ResponseMockConfig, ErrorConfig, ProxyConfig
from server.processors import ProcessingMeta
import server.processors.base as base
import utils

logger = getLogger(__name__)


ModelType = TypeVar("ModelType", bound=BaseModel)


async def render_simple_type(
    env: Environment,
    simple_type: Type[utils.SimpleType],
    value: utils.SimpleType,
) -> utils.SimpleType:
    rendered = await env.from_string(str(value)).render_async()
    try:
        return simple_type(rendered)
    except Exception:
        logger.error("Error parsing rendered data to required type")
        return value


async def render_list(env: Environment, values: list) -> list:
    result = []
    for item in values:
        if isinstance(item, list):
            result.append(await render_list(env, item))
        elif isinstance(item, dict):
            result.append(await render_dict(env, item))
        elif isinstance(item, str):
            result.append(await env.from_string(item).render_async())
        else:
            result.append(item)
    return result


async def render_dict(env: Environment, values: dict) -> dict:
    result = {}
    for key, value in values.items():
        if isinstance(value, list):
            result[key] = await render_list(env, value)
        elif isinstance(value, dict):
            result[key] = await render_dict(env, value)
        elif isinstance(value, str):
            result[key] = await env.from_string(value).render_async()
        else:
            result[key] = value
    return result


def create_model(
    entity_type: Type[ModelType], *args, **kwargs
) -> ModelType | None:
    try:
        return entity_type(*args, **kwargs)
    except ValidationError as e:
        logger.error(utils.get_msg_from_parts(
            "Invalid mock data format", utils.get_validation_err_msg(e))
        )
    return None


async def render_model_from_str(
    env: Environment, entity_type: Type[ModelType], value: str
) -> ModelType | None:
    rendered = await env.from_string(value).render_async()
    parsed = None
    try:
        parsed = utils.parse_from_yaml(rendered.encode())
    except YAMLError as e:
        logger.error(utils.get_msg_from_parts(
            "Error parsing YML of mock data", utils.get_yml_err_msg(e))
        )
    if parsed is None:
        return None
    if issubclass(entity_type, RootModel):
        return create_model(entity_type, root=parsed)
    elif isinstance(parsed, dict):
        return create_model(entity_type, **parsed)
    else:
        return create_model(entity_type, parsed)


async def render_model(
    env: Environment, entity_type: Type[ModelType], value: dict | list
) -> ModelType | None:
    if isinstance(value, list):
        rendered = await render_list(env, value)
    else:
        rendered = await render_dict(env, value)
    try:
        return entity_type.model_validate(rendered)
    except YAMLError as e:
        logger.error(utils.get_msg_from_parts(
            "Error parsing YML of mock data", utils.get_yml_err_msg(e))
        )
    except ValidationError as e:
        logger.error(utils.get_msg_from_parts(
            "Invalid mock data format", utils.get_validation_err_msg(e))
        )
    return None


class TemplateProcessor:
    def __init__(self, environment: Environment):
        self._env = environment
        self._state = c.TEMP_INITIAL_STATE

    async def render_error_config(self, error_config: ErrorConfig):
        code = StatusCode.UNKNOWN.value[0]
        if error_config.code is not None:
            code = await render_simple_type(self._env, int, error_config.code)

        details = await render_simple_type(
            self._env, int, error_config.details
        )
        return create_model(ErrorConfig, code=code, details=details)

    async def render_proxy_config(
        self, proxy_config: ProxyConfig
    ) -> base.ProxyMock:
        socket = await render_simple_type(self._env, str, proxy_config.socket)

        seconds_timeout = None
        if isinstance(proxy_config.seconds_timeout, float):
            seconds_timeout = proxy_config.seconds_timeout
        elif isinstance(proxy_config.seconds_timeout, str):
            seconds_timeout = await render_simple_type(
                self._env, str, proxy_config.socket
            )
        return create_model(
            base.ProxyMock, socket=socket, seconds_timeout=seconds_timeout
        )

    async def render_mock_config(
        self, mock_config: ResponseMockConfig | str
    ) -> base.ResponseMock:
        if isinstance(mock_config, str):
            return await render_model_from_str(
                self._env, base.ResponseMock, mock_config
            ) or base.ResponseMock()

        message = None
        if isinstance(mock_config.messages, str):
            message = await render_model_from_str(
                self._env, base.MessageMock, mock_config.messages
            )
        elif isinstance(mock_config.messages, dict | list):
            message = await render_model(
                self._env, base.MessageMock, mock_config.messages
            )
        if not message:
            message = base.MessageMock()

        metadata = None
        if isinstance(mock_config.trailing_meta, str):
            metadata = await render_model_from_str(
                self._env, base.MessageMock, mock_config.trailing_meta
            )
        elif isinstance(mock_config.trailing_meta, dict):
            metadata = await render_model(
                self._env, base.MetadataMock, mock_config.trailing_meta
            )
        if not metadata:
            metadata = base.MetadataMock()

        error = None
        if isinstance(mock_config.error, ErrorConfig):
            error = await self.render_error_config(mock_config.error)
        elif isinstance(mock_config.error, str):
            error = await render_model_from_str(
                self._env, base.ErrorMock, mock_config.error
            )

        seconds_delay = mock_config.seconds_delay
        if seconds_delay is not None:
            seconds_delay = await render_simple_type(
                self._env, float, mock_config.seconds_delay
            )

        proxy = None
        if isinstance(mock_config.proxy, ProxyConfig):
            proxy = await self.render_proxy_config(mock_config.proxy)
        elif isinstance(mock_config.proxy, str):
            proxy = await render_model_from_str(
                self._env, base.ProxyMock, mock_config.proxy
            )

        return create_model(
            base.ResponseMock,
            messages=message,
            trailing_meta=metadata,
            error=error,
            seconds_delay=seconds_delay,
            proxy=proxy,
        ) or base.ResponseMock()

    def _set_state(self, value: Any):
        self._state = value

    def _get_state(self) -> Any:
        return self._state

    def _fill_environment(
        self,
        requests: list[dict],
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        self._env.globals[c.TEMP_SOCKETS_KEY] = AccessibleVariable([
            socket_data.socket for socket_data in meta.server_config.sockets
        ])
        self._env.globals[c.TEMP_ALIAS_KEY] = meta.server_config.alias
        self._env.globals[c.TEMP_SERVICE_KEY] = AccessibleVariable(
            meta.service_data.model_dump()
        )
        self._env.globals[c.TEMP_METHOD_KEY] = AccessibleVariable(
            meta.method_data.model_dump()
        )
        self._env.globals[c.TEMP_METADATA_KEY] = AccessibleVariable(
            base.extract_invocation_metadata(context)
        )
        self._env.globals[c.TEMP_MESSAGES_KEY] = AccessibleVariable(requests)
        if len(requests) > 0:
            self._env.globals[c.TEMP_MESSAGE_KEY] = AccessibleVariable(
                requests[0]
            )
        else:
            self._env.globals[c.TEMP_MESSAGE_KEY] = None

        self._env.globals[c.TEMP_SET_STATE_KEY] = self._set_state
        self._env.globals[c.TEMP_GET_STATE_KEY] = self._get_state

    async def create_mock_data(
        self,
        requests: list[dict],
        context: ServicerContext,
        meta: ProcessingMeta,
    ):
        self._fill_environment(requests, context, meta)
        response_mock = await self.render_mock_config(meta.mock_config)
        meta.mock_data = response_mock
