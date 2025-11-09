import os
import json
import requests
import traceback
import threading
import xml.etree.ElementTree as ET
from typing import List, Any


__all__ = [
    "WolframAPIManager",
]


class WolframAPIManager:
    
    def __init__(
        self,
        wolfram_api_keys_path: str = "wolfram_api_keys.json",
    ):

        if not os.path.exists(wolfram_api_keys_path):
            raise FileNotFoundError(
                f"Wolfram API 密钥文件未找到: {wolfram_api_keys_path}"
            )
        
        app_id_list: List[str] = []
        with open(wolfram_api_keys_path, 'r', encoding='UTF-8') as f:
            try:
                data: Any = json.load(f)
                if not isinstance(data, list):
                    raise TypeError(
                        f"密钥文件 {wolfram_api_keys_path} 的根 "
                        f"应为 list (列表)，而不是 {type(data).__name__}。"
                    )
                app_id_list = data
            except json.JSONDecodeError:
                raise ValueError(f"无法解析 {wolfram_api_keys_path}，请检查 JSON 格式。")
        
        if not app_id_list:
            raise ValueError(
                f"密钥文件 {wolfram_api_keys_path} 为空列表。"
            )

        self._app_id_list = []
        for i, app_id in enumerate(app_id_list):
            if not isinstance(app_id, str) or not app_id:
                raise ValueError(
                    f"在 {wolfram_api_keys_path} 的 "
                    f"列表索引 {i} 处的值不是一个有效的、非空的 app_id 字符串。"
                )
            self._app_id_list.append(app_id)

        self._key_rotation_lock = threading.Lock()
        self._rotation_index = 0

    def _get_next_app_id(
        self,
    )-> str:

        with self._key_rotation_lock:
            app_id = self._app_id_list[self._rotation_index]
            self._rotation_index = (
                self._rotation_index + 1
            ) % len(self._app_id_list)
            return app_id
    
    def query(
        self,
        query: str,
        timeout: int,
    )-> str:

        app_id: str = ""
        try:
            app_id = self._get_next_app_id()
        except Exception as e:
            return f"获取 Wolfram Alpha APP_ID 失败: {e}"
        
        base_url = 'http://api.wolframalpha.com/v2/query'
        params = {
            'input': query,
            'appid': app_id,
            'format': 'plaintext',
            'output': 'xml'
        }
        
        try:
            response = requests.get(base_url, params=params, timeout=timeout)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            
            if root.get('success') == 'false':
                error_message = root.find('.//error/msg')
                if error_message is not None and error_message.text:
                    return f"Wolfram Alpha API 错误: {error_message.text}"
                else:
                    return "Wolfram Alpha API 错误: 未知的 API 错误。"
            
            else:
                result_text: List[str] = []
                for pod in root.findall('.//pod'):
                    title = pod.get('title')
                    for subpod in pod.findall('.//subpod'):
                        plaintext = subpod.find('plaintext')
                        if plaintext is not None and plaintext.text:
                            result_text.append(f"{title}: {plaintext.text.strip()}")
                
                if not result_text:
                    return "Wolfram Alpha 未找到有效结果。"
                else:
                    return "\n".join(result_text)
        
        except requests.exceptions.Timeout:
            return f"Wolfram Alpha API 请求超时 (超过 {timeout} 秒)。"
        except requests.exceptions.RequestException as e:
            return f"网络或 API 请求错误: {e}"
        except ET.ParseError as e:
            return f"解析 XML 响应失败: {e}"
        except Exception as error:
            return (
                f"查询 Wolfram Alpha 时发生意外错误: {error}\n"
                f"调用栈：\n{traceback.format_exc()}"
            )