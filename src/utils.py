import logging
import os

import yaml
from pydantic import ValidationError
from yaml import YAMLError

logger = logging.getLogger(__name__)


SimpleType = int | str | float | bool


def get_relative_abs_path(base_dir: str, file_path: str):
    if not os.path.isabs(file_path):
        return os.path.normpath(
            os.path.join(os.path.abspath(base_dir), file_path)
        )
    return file_path


def get_msg_from_parts(*parts, default: str | None = None) -> str:
    result = ". ".join(parts)
    if not result:
        if not default:
            result = "Unexpected internal error"
        else:
            result = default
    return result


def get_yml_err_msg(err: YAMLError) -> str:
    return str(err)


def get_validation_err_msg(err: ValidationError) -> str:
    error_details = err.errors()
    parts = []
    for error_detail in error_details:
        result_error = ""
        message = error_detail.get("msg")
        location = None

        location_data = error_detail.get("loc")
        if location_data:
            location = " -> ".join([str(v) for v in location_data])
        if location and message:
            result_error = f"{location}: {message}"
        elif location:
            result_error = f"Unknown error at {location}"
        elif message:
            result_error = message
        if result_error:
            parts.append(result_error)
    return get_msg_from_parts(*parts, default="Unknown validation error")


def get_io_err_msg(exception: Exception) -> str:
    parts = []
    for argument in exception.args:
        if argument is not None and not isinstance(argument, int):
            parts.append(str(argument))
    return get_msg_from_parts(*parts)


def get_unknown_err_msg(exception: Exception) -> str:
    parts = []
    for argument in exception.args:
        if argument is not None:
            parts.append(str(argument))
    return get_msg_from_parts(*parts)


def get_exception_error(exception: Exception) -> str:
    if isinstance(exception, IOError):
        return get_io_err_msg(exception)
    elif isinstance(exception, YAMLError):
        return get_yml_err_msg(exception)
    else:
        return get_unknown_err_msg(exception)


def read_file_bytes(filepath: str) -> bytes:
    try:
        with open(filepath, "rb") as file:
            return file.read()
    except IOError as e:
        error_data = get_exception_error(e)
        message = f"File '{filepath}' reading error"
        if error_data:
            message = f"{message}. {error_data}"
        raise IOError(message)


def read_file(filepath: str, encoding: str | None = None) -> str:
    try:
        with open(filepath, "r", encoding=encoding) as file:
            return file.read()
    except IOError as e:
        error_data = get_exception_error(e)
        message = f"File '{filepath}' reading error"
        log_message = message
        if error_data:
            log_message = f"{message}. {error_data}"

        logger.error(log_message)

        raise IOError(message)


def parse_from_yaml(value: bytes) -> dict:
    try:
        return yaml.safe_load(value)
    except Exception as e:
        raise IOError(
            "YAML parsing error. " + get_exception_error(e)
        )
