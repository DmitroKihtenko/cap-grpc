import importlib
import sys
from functools import lru_cache
from importlib.util import spec_from_loader
from types import ModuleType

from protobuf.definitions import GeneratedData


class InMemoryLoader(importlib.abc.Loader):
    def __init__(self, source_files: dict[str, str]):
        self._source_files = source_files

    def exec_module(self, module):
        filename = module.__name__ + ".py"
        if filename in self._source_files:
            content = self._source_files[filename]
            exec(content, module.__dict__)
        return None


class InMemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self):
        self._source_files = {}

    def add_source_files(self, source_files: dict[str, str]):
        self._source_files.update(source_files)


    def clear_source_files(self):
        self._source_files = {}

    def find_spec(self, fullname, path, target=None):
        filename = fullname + ".py"
        if filename in self._source_files:
            spec = spec_from_loader(fullname, InMemoryLoader(self._source_files))
            return spec


@lru_cache
def get_in_memory_finder() -> InMemoryFinder:
    finder = InMemoryFinder()
    sys.meta_path.insert(0, finder)
    return finder


def import_in_memory_module_code(
    generated_data: GeneratedData
) -> dict[str, ModuleType]:
    result = {}
    get_in_memory_finder().add_source_files(generated_data.source_files)
    for python_file, source_code_content in generated_data.source_files.items():
        result[python_file] = ModuleType(python_file)
        exec(source_code_content, result[python_file].__dict__)
    get_in_memory_finder().clear_source_files()
    return result
