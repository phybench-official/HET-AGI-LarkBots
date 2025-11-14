from .typing import *
from .externals import *


__all__ = [
    "align_image_to_bytes",
    "align_image_to_bytes_async",
]


def align_image_to_bytes(
    image: Any,
)-> bytes:
    
    image_type: str = ""
    if isinstance(image, bytes):
        image_type = "bytes"
    elif isinstance(image, str):
        if image.startswith("http://") or image.startswith("https://"):
            image_type = "url"
        else:
            image_type = "file"
    else:
        raise NotImplementedError(
            f"无法处理类型为 {type(image).__name__} 的图片！"
        )

    if image_type == "bytes":
        assert isinstance(image, bytes)
        return image
    elif image_type == "file":
        assert isinstance(image, str)
        with open(image, "rb") as file_pointer:
            image_bytes: bytes = file_pointer.read()
        return image_bytes
    elif image_type == "url":
        raise NotImplementedError

    raise RuntimeError("图片对齐逻辑出现未知错误。")


async def align_image_to_bytes_async(
    image: Any,
)-> bytes:
    
    image_type: str = ""
    if isinstance(image, bytes):
        image_type = "bytes"
    elif isinstance(image, str):
        if image.startswith("http://") or image.startswith("https://"):
            image_type = "url"
        else:
            image_type = "file"
    else:
        raise NotImplementedError(
            f"无法处理类型为 {type(image).__name__} 的图片！"
        )
    
    if image_type == "bytes":
        assert isinstance(image, bytes)
        return image
    elif image_type == "file":
        assert isinstance(image, str)
        async with aiofiles.open(image, "rb") as file_pointer:
            image_bytes: bytes = await file_pointer.read()
        return image_bytes
    elif image_type == "url":
        raise NotImplementedError

    raise RuntimeError("图片对齐逻辑出现未知错误。")