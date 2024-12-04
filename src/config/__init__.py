from pydantic import ValidationError

from config.model import Config
from utils import get_validation_err_msg, get_exception_error


def parse_config(raw_config: dict) -> Config:
    try:
        config = Config.model_validate(raw_config)
        return config
    except ValidationError as e:
        raise IOError(
            "Config file parsing error. " +
            get_validation_err_msg(e)
        )
    except ValueError as e:
        raise IOError(
            "Config file parsing error. " +
            get_exception_error(e)
        )
