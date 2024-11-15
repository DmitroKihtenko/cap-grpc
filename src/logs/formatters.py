import re
from datetime import datetime
import logging
from typing import Set, Iterable

import yaml


class YamlFormatter(logging.Formatter):
    def __init__(self, used_keys: Iterable | str = None, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)

        if isinstance(used_keys, str):
            pattern = r"%\(([^)]+)\)s"
            used_keys = re.findall(pattern, used_keys)
        elif used_keys is None:
            used_keys = {"msg"}
        self.used_keys = used_keys

    @property
    def used_keys(self) -> Set[str]:
        return self.__used_keys

    @used_keys.setter
    def used_keys(self, keys: Set[str]):
        self.__used_keys = keys

    def format_fields(self, record: logging.LogRecord) -> dict:
        values = dict(record.__dict__)
        values.pop("args")
        if record.args:
            values["msg"] = record.msg % record.args
            if "color_message" in values.keys():
                values["color_message"] = values["color_message"] % record.args

        return values

    def add_fields(self, record: dict) -> dict:
        record["timestamp"] = datetime.fromtimestamp(
            record.get("created")
        ).isoformat()
        return record

    def format(self, record: logging.LogRecord) -> str:
        record_dict = self.format_fields(record)
        record_dict = self.add_fields(record_dict)
        for key in set(record_dict.keys()):
            if key not in self.used_keys:
                record_dict.pop(key)
        result = yaml.safe_dump([record_dict])
        return result
