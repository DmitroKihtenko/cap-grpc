import re

PY_LOGS_FORMAT_PATTERN = re.compile(r"%\(([^)]+)\)s")
ALLOWED_LOGGING_KEYS = {
    "alias", "created", "exc_info", "exc_text", "filename", "code", "message",
    "funcName", "levelname", "levelno", "lineno", "metadata", "method",
    "module", "msecs", "msg", "name", "pathname", "error_details", "process",
    "processName", "relativeCreated", "service", "stack_info", "taskName",
    "thread", "threadName", "timestamp", "request_message", "response_message",
}

RPC_HEADER_KEY_PATTERN = re.compile(r"^[a-z0-9-_.]{1,256}$")
RPC_HEADER_VALUE_PATTERN = re.compile(r"^[a-z0-9-_.]{0,8192}$")

DESCRIPTOR_TEMP_FILENAME = "descriptor.pb"

TEMP_BASE_DIR_KEY = "directory"
TEMP_FILES_CACHE_KEY = "files_cache"

TEMP_RELATIVE_KEY = "relative"
TEMP_INSERT_KEY = "insert"
TEMP_SCRIPT_KEY = "shell"
TEMP_SET_STATE_KEY = "set_state"
TEMP_GET_STATE_KEY = "get_state"
TEMP_INITIAL_STATE = "initial"
TEMP_SOCKETS_KEY = "sockets"
TEMP_ALIAS_KEY = "alias"
TEMP_SERVICE_KEY = "service"
TEMP_METHOD_KEY = "method"
TEMP_METADATA_KEY = "metadata"
TEMP_MESSAGES_KEY = "messages"
TEMP_MESSAGE_KEY = "message"
