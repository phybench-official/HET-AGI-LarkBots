from .json_tools import *
from .lark_sdk import *
from .typing import *


__all__ = [
    "get_lark_app_token",
]


def get_lark_app_token(
    app: str,
)-> Tuple[str, str]:
    
    app_token_dict = load_from_json("lark_api_keys.json")
    app_id = app_token_dict[app]["app_id"]
    app_secret = app_token_dict[app]["app_secret"]
    return app_id, app_secret


