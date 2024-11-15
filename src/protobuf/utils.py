import re


def get_python_spec_by_proto_path(relative_path: str) -> set[str]:
    replace_suffix = ".proto"
    spec_suffixes = ["_pb2.py", "_pb2_grpc.py"]
    dir_symbols_exp = "[\\/]+"
    dir_symbols_replace = "."
    symbols_exp = f"[^a-zA-Z0-9\\{dir_symbols_replace}]"
    symbols_replace = "_"

    result = set()

    for suffix in spec_suffixes:
        python_spec = relative_path.removesuffix(replace_suffix)
        python_spec = re.sub(dir_symbols_exp, dir_symbols_replace, python_spec)
        python_spec = re.sub(symbols_exp, symbols_replace, python_spec)
        python_spec += suffix

        result.add(python_spec)
    return result
