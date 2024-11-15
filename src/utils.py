import logging
import os

logger = logging.getLogger(__name__)


def get_path_relative_to_config(config_file_dir: str, file_path: str):
    if not os.path.isabs(file_path):
        return os.path.normpath(
            os.path.join(os.path.abspath(config_file_dir), file_path)
        )
    return file_path


def get_exception_parts(exception: Exception) -> list[str]:
    parts = list()
    if isinstance(exception, IOError):
        for argument in exception.args:
            if argument is not None and not isinstance(argument, int):
                parts.append(str(argument))
    else:
        for argument in exception.args:
            if argument is not None:
                parts.append(str(argument))
    return parts


def get_exception_error(exception: Exception) -> str:
    return ". ".join(get_exception_parts(exception))


def read_file_bytes(filepath: str) -> bytes:
    try:
        with open(filepath, "rb") as file:
            return file.read()
    except IOError as e:
        error_data = get_exception_error(e)
        message = f"Config file '{filepath}' reading error"
        if error_data:
            message = f"{message}. {error_data}"
        raise IOError(message)


def read_file(filepath: str) -> str:
    try:
        with open(filepath, "r") as file:
            return file.read()
    except IOError as e:
        error_data = get_exception_error(e)
        message = f"Config file '{filepath}' reading error"
        log_message = message
        if error_data:
            log_message = f"{message}. {error_data}"

        logger.error(log_message)

        raise IOError(message)
