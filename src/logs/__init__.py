import logging
from logging import Logger, Handler, PlaceHolder

from pydantic import BaseModel, ConfigDict

REQUESTS_MOCK_LOG_PREFIX = "mock_requests"


def get_logger_name(parts: list[str]) -> str:
    return ".".join(parts)


class LoggerConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    level: int | str | None = None
    disabled: bool | None = None
    handlers: list[Handler] | None = None


def configure_logger(
    logger: Logger,
    level: int | str | None = None,
    disabled: bool | None = None,
    handlers: list[Handler] | None = None,
):
    if level is not None:
        logger.setLevel(level)
    if disabled is not None:
        logger.disabled = disabled
    if handlers is not None:
        logger.handlers.clear()
        logger.handlers.extend(handlers)


def configure_logger_by_name(
    logger_name: str,
    level: int | str | None = None,
    disabled: bool | None = None,
    handlers: list[Handler] | None = None,
):
    logger = logging.getLogger(logger_name)
    configure_logger(logger, level, disabled, handlers)


def configure_all(
    level: int | str | None = None,
    disabled: bool | None = None,
    handlers: list[Handler] | None = None
):
    for logger in logging.root.manager.loggerDict.values():
        if not isinstance(logger, PlaceHolder):
            configure_logger(logger, level, disabled, handlers)


def configure_by_prefix(
    prefix: str,
    level: int | str | None = None,
    disabled: bool | None = None,
    handlers: list[Handler] | None = None,
):
    for logger_name, logger in logging.root.manager.loggerDict.items():
        if logger_name.startswith(prefix) and not isinstance(
            logger, PlaceHolder
        ):
            configure_logger(logger, level, disabled, handlers)
