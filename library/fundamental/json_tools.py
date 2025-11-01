import json
from typing import Any


__all__ = [
    "save_to_json",
    "load_from_json",
    "serialize_json",
    "deserialize_json",
]


def save_to_json(
    obj: Any,
    file_path: str,
    encoding: str = "UTF-8",
)-> None:
    
    with open(
        file = file_path,
        mode = "w",
        encoding = encoding,
    ) as file_pointer:
        json.dump(obj, file_pointer)


def load_from_json(
    file_path: str,
    encoding: str = "UTF-8",
)-> Any:
    
    with open(
        file = file_path,
        mode = "r",
        encoding = encoding,
    ) as file_pointer:
        obj = json.load(file_pointer)
    
    return obj


serialize_json = lambda obj: json.dumps(
    obj,
    ensure_ascii = False,
)


deserialize_json = json.loads