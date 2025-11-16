"""
MCP 服务器配置管理模块

负责加载和管理 MCP 服务器的配置信息。
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


__all__ = [
    "MCPServerConfig",
    "get_server_config",
    "load_mcp_config",
]


@dataclass
class MCPServerConfig:
    """MCP 服务器配置数据类"""

    url: str
    auth_token: Optional[str] = None
    timeout: float = 120.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "auth_token": self.auth_token,
            "timeout": self.timeout,
        }


def load_mcp_config(config_path: str = "mcp_servers_config.json") -> Dict[str, Any]:
    """
    加载 MCP 服务器配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典

    Raises:
        FileNotFoundError: 配置文件不存在
        json.JSONDecodeError: 配置文件格式错误
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(
            f"MCP 配置文件不存在: {config_path}\n"
            f"请确保配置文件存在，并包含服务器连接信息。"
        )

    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return config


def get_server_config(
    server_name: str,
    config_path: str = "mcp_servers_config.json"
) -> MCPServerConfig:
    """
    获取指定服务器的配置

    Args:
        server_name: 服务器名称（如 "mathematica"）
        config_path: 配置文件路径

    Returns:
        MCP 服务器配置对象

    Raises:
        FileNotFoundError: 配置文件不存在
        KeyError: 服务器配置不存在
        ValueError: 配置格式错误
    """
    config = load_mcp_config(config_path)

    # 兼容两种配置格式：
    # 1. {"servers": {"mathematica": {...}}}  (带 servers 层级)
    # 2. {"mathematica": {...}}  (直接配置)
    if "servers" in config:
        servers_config = config["servers"]
    else:
        servers_config = config

    # 查找服务器配置
    if server_name not in servers_config:
        available_servers = ", ".join(servers_config.keys())
        raise KeyError(
            f"未找到服务器 '{server_name}' 的配置。\n"
            f"可用的服务器: {available_servers}"
        )

    server_config = servers_config[server_name]

    # 验证必需字段
    if "url" not in server_config:
        raise ValueError(
            f"服务器 '{server_name}' 的配置缺少必需字段 'url'"
        )

    # 构建配置对象
    return MCPServerConfig(
        url=server_config["url"],
        auth_token=server_config.get("auth_token"),
        timeout=server_config.get("timeout", 120.0),
    )
