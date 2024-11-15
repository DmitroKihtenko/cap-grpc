from pydantic import ValidationError

from constants import RPC_HEADER_KEY_PATTERN


def validate_grpc_meta_key(key: str) -> str:
    if not RPC_HEADER_KEY_PATTERN.match(key):
        raise ValueError(
            "gRPC header key should contain only lowercase latin "
            "symbols, numbers and symbols -_. with length 1-256"
        )
    return key


def validate_grpc_meta_value(value: str) -> str:
    if not RPC_HEADER_KEY_PATTERN.match(value):
        raise ValueError(
            "gRPC header key should contain only lowercase latin "
            "symbols, numbers and symbols -_. with length 1-8192"
        )
    return value


def validate_grpc_error_status_code(value: int) -> int:
    if value < 1 or value > 16:
        raise ValueError("gRPC error status code should be from 1 to 16")
    return value


def get_validation_error_message(error: ValidationError) -> str:
    error_details = error.errors()
    result = []
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
            result.append(result_error)
    if len(result) > 0:
        return ". ".join(result)
    else:
        return "Unknown validation error"
