from glob import glob, has_magic
import os

from config.model import ServerConfig
from protobuf.definitions import ProtoFilesPaths
from utils import get_relative_abs_path


def get_proto_files_paths(
    server_config: ServerConfig, config_file_dir: str,
) -> ProtoFilesPaths:
    if isinstance(server_config.proto_files, str):
        file_paths = [server_config.proto_files]
    else:
        file_paths = server_config.proto_files

    base_dir_path = server_config.proto_files_base_dir
    abs_file_paths = set()
    result_file_paths = set()

    for file_path in file_paths:
        abs_file_paths.add(get_relative_abs_path(
            config_file_dir, file_path,
        ))

    if not base_dir_path:
        base_dir_path = os.path.dirname(os.path.commonprefix(list(
            abs_file_paths
        )))
    elif not os.path.isabs(base_dir_path):
        base_dir_path = os.path.normpath(
            os.path.join(os.path.abspath(config_file_dir), base_dir_path)
        )
    for file_path in abs_file_paths:
        if has_magic(file_path):
            paths = glob(file_path, recursive=True)
            for path in paths:
                result_file_paths.add(path)
        else:
            result_file_paths.add(file_path)

    return ProtoFilesPaths(
        base_dir_abs=base_dir_path,
        proto_files_abs=result_file_paths,
    )