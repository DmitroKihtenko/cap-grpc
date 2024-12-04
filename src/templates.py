import asyncio
import json
import os
from asyncio.subprocess import create_subprocess_exec
from copy import deepcopy
from logging import getLogger
from typing import Callable

from jinja2 import BaseLoader, Environment, pass_context
from jinja2.runtime import Context

import constants as c
from utils import read_file, get_relative_abs_path, get_exception_error

logger = getLogger(__name__)


class AccessibleVariable:
    def __init__(self, obj: dict | list):
        self._raw_obj = obj
        self._obj = deepcopy(obj)
        self._is_dict = isinstance(self._obj, dict)
        if self._is_dict:
            for k in self._obj.keys():
                if isinstance(self._obj[k], list | dict):
                    self._obj[k] = AccessibleVariable(self._obj[k])
        elif isinstance(self._obj, list):
            for index in range(len(self._obj)):
                if isinstance(self._obj[index], list | dict):
                    self._obj[index] = AccessibleVariable(self._obj[index])
        else:
            self._raw_obj = {}
            self._obj = {}

    def __getattr__(self, key):
        if self._is_dict:
            return self._obj.get(key)
        try:
            key = int(key)
        except KeyError:
            return None
        if len(self._obj) > key:
            return self._obj[key]
        return None

    def __getitem__(self, key):
        if self._is_dict:
            return self._obj.get(str(key))
        if len(self._obj) > key:
            return self._obj[key]
        return None

    def __iter__(self):
        if self._is_dict:
            return iter(self._obj.items())
        else:
            return iter(self._obj)

    def keys(self):
        if self._is_dict:
            return list(self._obj.keys())
        else:
            return [index for index in range(len(self._obj))]

    def values(self):
        if self._is_dict:
            return list(self._obj.values())
        else:
            return self._obj

    def items(self):
        if self._is_dict:
            return list(self._obj.items())
        else:
            return [(k, self._obj[k]) for k in range(len(self._obj))]

    def __str__(self):
        return json.dumps(self._raw_obj)


class AnyPathFSLoader(BaseLoader):
    def __init__(self, base_dir: str):
        self._base_dir = base_dir

    @property
    def base_dir(self) -> str:
        return self._base_dir

    @base_dir.setter
    def base_dir(self, base_dir: str):
        self._base_dir = base_dir

    def get_source(
        self, environment: Environment, template: str
    ) -> tuple[str, str | None, Callable[[], bool] | None]:
        source = ""
        try:
            if os.path.isabs(template):
                source = read_file(template)
            else:
                source = read_file(os.path.join(self.base_dir, template))
        except IOError:
            pass
        return source, template, lambda: True


@pass_context
def get_file_content(
    context: Context,
    path: str,
    encoding: str | None = None,
    use_cache: bool = True,
) -> str | None:
    base_dir = context.get(c.TEMP_BASE_DIR_KEY, "")
    files = context.get(c.TEMP_FILES_CACHE_KEY, None)
    if files is None and use_cache:
        logger.error("Error using files cache")
        use_cache = False
    try:
        file_path = get_relative_abs_path(base_dir, path)
        if use_cache:
            if file_path not in files:
                file_data = read_file(file_path, encoding)
                files[file_path] = file_data
            return files[file_path]
        else:
            return read_file(file_path, encoding)
    except IOError:
        return None


@pass_context
def get_relative_path(context: Context, file_name: str) -> str | None:
    base_dir = context.get(c.TEMP_BASE_DIR_KEY, "")
    try:
        return get_relative_abs_path(base_dir, file_name)
    except Exception as e:
        logger.error(get_exception_error(e))


async def run_shell_script(
    program: str, *args, stdin: str | None = None
) -> AccessibleVariable | None:
    try:
        process = await create_subprocess_exec(
            program,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdin_bytes = None
        if stdin is not None:
            stdin_bytes = stdin.encode()
        stdout, stderr = await process.communicate(input=stdin_bytes)
        return AccessibleVariable({
            "code": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
        })
    except Exception as e:
        logger.error(get_exception_error(e))
        return None


def create_base_environment(base_dir: str) -> Environment:
    result = Environment(
        loader=AnyPathFSLoader(base_dir),
        enable_async=True,
    )
    result.globals[c.TEMP_BASE_DIR_KEY] = base_dir
    result.globals[c.TEMP_FILES_CACHE_KEY] = {}
    result.globals[c.TEMP_RELATIVE_KEY] = get_relative_path
    result.globals[c.TEMP_INSERT_KEY] = get_file_content
    result.globals[c.TEMP_SCRIPT_KEY] = run_shell_script

    return result
