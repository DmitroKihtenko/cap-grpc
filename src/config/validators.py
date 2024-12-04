import constants as c


def validate_grpc_meta_key(key: str) -> str:
    if not c.RPC_HEADER_KEY_PATTERN.match(key):
        raise ValueError(
            "gRPC metadata key should contain only lowercase latin "
            "symbols, numbers and symbols -_. with length 1-256"
        )
    return key


def validate_grpc_meta_value(value: str) -> str:
    if not c.RPC_HEADER_VALUE_PATTERN.match(value):
        raise ValueError(
            "gRPC metadata value should contain only lowercase latin "
            "symbols, numbers and symbols -_. with length 1-8192"
        )
    return value


def validate_grpc_error_status_code(value: int) -> int:
    if value < 1 or value > 16:
        raise ValueError("gRPC error status code should be from 1 to 16")
    return value


def validate_logging_keys(message_format: str):
    used_keys = set(c.PY_LOGS_FORMAT_PATTERN.findall(message_format))
    invalid_keys = used_keys.difference(c.ALLOWED_LOGGING_KEYS)
    if len(invalid_keys) > 0:
        raise ValueError(
            f"Logging keys are not allowed: '{"', '".join(invalid_keys)}'. "
            "Allowed logging keys are: "
            f"'{"', '".join(c.ALLOWED_LOGGING_KEYS)}'"
        )
    return message_format
