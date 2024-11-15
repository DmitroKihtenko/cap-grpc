import re

RPC_HEADER_KEY_PATTERN = re.compile(r'^[a-z0-9-_.]{1,256}$')
RPC_HEADER_VALUE_PATTERN = re.compile(r'^[a-z0-9-_.]{0,8192}$')
