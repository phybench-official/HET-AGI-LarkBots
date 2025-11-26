import pandas as pd
from typing import Any


__all__ = [
    "load_from_parquet",
    "save_to_parquet",
]


def load_from_parquet(
    parquet_path: str, 
)-> pd.DataFrame:
    
    return pd.read_parquet(
        parquet_path, 
        engine = "pyarrow", 
    )


def save_to_parquet(
    obj: Any,
    /,
    parquet_path: str, 
    index: bool = False, 
    row_group_size: int = 10,
)-> None:
    
    if not isinstance(obj, pd.DataFrame):
        obj = pd.DataFrame(obj)

    obj.to_parquet(
        parquet_path,
        engine = "pyarrow",
        compression = "snappy",
        index = index,
        row_group_size = row_group_size,
    )