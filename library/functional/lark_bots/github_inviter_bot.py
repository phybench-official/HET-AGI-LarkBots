import json
import os
import aiohttp
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from collections import OrderedDict
import asyncio

from ...fundamental import *
from ...fundamental.lark_tools._lark_sdk import P2ContactUserCreatedV3

__all__ = [
    "GithubInviterBot",
]

_launch_time_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class GithubInviterBot(ParallelThreadLarkBot):

    def __init__(
        self,
        config_path: str,
        image_cache_size: int = 128,
        worker_timeout: float = 3600.0,
        context_cache_size: int = 1024,
        max_workers: Optional[int] = None,
    )-> None:

        super().__init__(
            config_path = config_path,
            image_cache_size = image_cache_size,
            worker_timeout = worker_timeout,
            context_cache_size = context_cache_size,
            max_workers = max_workers,
        )
        
        # 保持与父类进程隔离逻辑一致
        self._init_arguments: Dict[str, Any] = {
            "config_path": config_path,
            "image_cache_size": image_cache_size,
            "worker_timeout": worker_timeout,
            "context_cache_size": context_cache_size,
            "max_workers": max_workers,
        }
        
        self._mention_me_text = f"@{self._config['name']}"
        self._github_base_url = "https://api.github.com"
        self._http_session: Optional[aiohttp.ClientSession] = None
        
        # 纯内存存储用户绑定关系 (Feishu OpenID -> Github Username)
        self._user_mapping: Dict[str, str] = {}
        # 读写锁，确保并发安全
        self._mapping_lock = asyncio.Lock()
        
        # 注册飞书新人入群/入租户事件
        self.register_user_created(self._handle_user_created_bridge)


    async def _get_session(self)-> aiohttp.ClientSession:
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        chat_type = parsed_message["chat_type"]
        is_thread_root = parsed_message["is_thread_root"]
        
        # 仅处理私聊消息的根消息
        if chat_type == "p2p" and is_thread_root:
            return True
        return False
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:
        return {
            "is_tombstone": False,
            "lock": asyncio.Lock(), 
            "thread_root_id": thread_root_id,
            "history": [],
            "running_workflows": 0,
            "is_archived": False,
        }
    

    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:

        message_id: str = parsed_message["message_id"]
        text: str = parsed_message["text"].strip()
        
        if text.startswith("/"):
            await self._handle_command(parsed_message)
        else:
            await self.reply_message_async(
                response = "Magnus 仅接受指令操作。\n发送 /join_github <github_username> 申请加入组织，或 /help 查看帮助。",
                message_id = message_id,
            )

        return context
    

    async def _handle_command(
        self,
        parsed_message: Dict[str, Any],
    ) -> None:
        
        message_id = parsed_message["message_id"]
        text = parsed_message["text"]
        sender = parsed_message["sender"]
        
        # 实时从 config 读取管理员列表
        admin_list = self._config.get("admin_open_ids", [])
        is_admin = sender in admin_list

        await self._execute_command(
            command_line = text,
            message_id = message_id,
            is_admin = is_admin,
            sender_id = sender,
        )
    

    async def _execute_command(
        self,
        command_line: str,
        message_id: str,
        is_admin: bool,
        sender_id: Optional[str],
    )-> None:
        
        args = command_line.split()
        if not args: return
        command = args[0].lower()

        # === 基础指令 /me ===
        if command == "/me":
            role = "管理员 (Admin)" if is_admin else "普通用户 (User)"
            
            # 加锁读取绑定状态
            bound_account = "未绑定"
            if sender_id:
                async with self._mapping_lock:
                    bound_account = self._user_mapping.get(sender_id, "未绑定")

            response_text = (
                f"[用户档案]\n"
                f"OpenID:   {sender_id}\n"
                f"权限身份: {role}\n"
                f"GitHub账号: {bound_account}\n"
            )
            await self.reply_message_async(response_text, message_id)
            return

        # === 基础指令 /you ===
        elif command == "/you":
            org_name = self._config.get("github_org_name", "Unknown")
            response_text = (
                f"[Magnus 系统信息]\n"
                f"机器人ID: {self._config.get('open_id', 'Unknown')}\n"
                f"服务组织: {org_name}\n"
                f"启动时间: {_launch_time_stamp}\n"
            )
            await self.reply_message_async(response_text, message_id)
            return

        # === 基础指令 /help ===
        elif command == "/help":
            help_text = (
                "Magnus 指令列表：\n"
                "  /me                      查看个人档案\n"
                "  /you                     查看机器人信息\n"
                "  /join_github <username>  申请加入 GitHub 组织\n"
            )
            # 仅管理员可见
            if is_admin:
                help_text += (
                    "\n管理员指令：\n"
                    "  /update_config [path]    热重载配置文件\n"
                )
            await self.reply_message_async(help_text, message_id)
            return

        # === 管理指令 /update_config ===
        elif command == "/update_config":
            if not is_admin:
                await self.reply_message_async("错误: 权限不足 (EACCES)", message_id)
                return
            
            target_path = args[1] if len(args) > 1 else self._config_path
            await self.reply_message_async("正在重新加载配置文件...", message_id)
            
            try:
                # 调用父类方法重载配置
                new_config_content = await self._reload_config_async(target_path)
                await self.reply_message_async(
                    f"Magnus 配置更新成功！\n读取路径: {self._config_path}", 
                    message_id
                )
            except Exception as e:
                await self.reply_message_async(f"配置更新失败: {e}", message_id)
            return

        # === 核心指令 /join_github ===
        elif command == "/join_github":
            if len(args) < 2:
                await self.reply_message_async("用法: /join_github <github_username>", message_id)
                return
            
            target_username = args[1]
            
            # 唯一绑定检查 (加锁读取)
            if sender_id:
                async with self._mapping_lock:
                    if sender_id in self._user_mapping:
                        bound_username = self._user_mapping[sender_id]
                        if bound_username.lower() != target_username.lower():
                            await self.reply_message_async(
                                f"❌ 操作失败：您已绑定账号 '{bound_username}'。\n如需更换请联系管理员。", 
                                message_id
                            )
                            return
            
            invite_role = "admin" if is_admin else "direct_member"
            
            await self._invite_user_to_github(
                username = target_username, 
                role = invite_role, 
                message_id = message_id,
                sender_id = sender_id
            )
            return
        
        else:
            await self.reply_message_async(f"Magnus 未知指令: {command}", message_id)


    async def _invite_user_to_github(
        self,
        username: str,
        role: str,
        message_id: str,
        sender_id: Optional[str],
    )-> None:
        
        # 每次直接从 config 读取，支持热更新
        github_token = self._config.get("github_token")
        org_name = self._config.get("github_org_name")
        
        if not github_token or not org_name:
            await self.reply_message_async("Magnus 配置错误：缺少 github_token 或 github_org_name", message_id)
            return

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
        }
        
        session = await self._get_session()
        
        # 1. Resolve Username to ID
        user_url = f"{self._github_base_url}/users/{username}"
        try:
            async with session.get(user_url, headers=headers) as resp:
                if resp.status != 200:
                    await self.reply_message_async(f"查找用户 '{username}' 失败，请确认拼写。", message_id)
                    # 查找失败不绑定
                    return
                user_data = await resp.json()
                user_id = user_data.get("id")
        except Exception as e:
            print(f"[Magnus] Network Error: {e}")
            await self.reply_message_async("Magnus 网络请求出错，请联系管理员。", message_id)
            return

        if not user_id:
            await self.reply_message_async(f"未找到用户 ID。", message_id)
            return

        # 2. Send Invitation
        invite_url = f"{self._github_base_url}/orgs/{org_name}/invitations"
        payload = {"invitee_id": user_id, "role": role}

        try:
            async with session.post(invite_url, headers=headers, json=payload) as resp:
                is_success = False
                
                if resp.status == 201:
                    role_display = "管理员" if role == "admin" else "成员"
                    await self.reply_message_async(
                        f"✅ 已向 {username} 发送 {role_display} 邀请。\n请检查 GitHub 注册邮箱。",
                        message_id
                    )
                    is_success = True
                        
                elif resp.status == 422:
                    await self.reply_message_async(
                        "⚠️ 邀请未发送：用户已在组织中或有待处理邀请。",
                        message_id
                    )
                    # 422 意味着用户存在且关联有效，视为成功，允许绑定
                    is_success = True
                else:
                    error_text = await resp.text()
                    print(f"[Magnus] Invite Failed: {resp.status} | {error_text}")
                    await self.reply_message_async(f"❌ 邀请失败 (Code: {resp.status})。请联系管理员。", message_id)
                    is_success = False

                # 3. 只有操作成功才绑定，防止输错用户名锁死
                if is_success and sender_id:
                    async with self._mapping_lock:
                        if sender_id not in self._user_mapping:
                            self._user_mapping[sender_id] = username
                            print(f"[Magnus] Bound user {sender_id} to {username}")

        except Exception as e:
            print(f"[Magnus] Network Error: {e}")
            await self.reply_message_async("网络请求出错，请联系管理员。", message_id)


    # === 新人加入事件处理 ===
    
    def _handle_user_created_bridge(
        self,
        event: P2ContactUserCreatedV3,
    )-> None:
        assert self._async_loop is not None
        asyncio.run_coroutine_threadsafe(
            self._handle_user_created_async(event),
            self._async_loop,
        )
    
    
    async def _handle_user_created_async(
        self,
        event: P2ContactUserCreatedV3,
    )-> None:
        try:
            if not event.event or not event.event.object: return
            user_id = event.event.object.user_id
            if not user_id: return

            # 每次读取最新配置
            org_name = self._config.get("github_org_name", "该组织")
            
            print(f"[Magnus] Detected new user: {user_id}")
            
            welcome_text = (
                f"欢迎加入 {org_name}！\n"
                f"我是 Magnus Bot。回复指令：\n"
                f"/join_github <您的GitHub用户名>\n"
                f"我将邀请您加入 {org_name} GitHub 组织，邀请函会发至您的 Github 绑定邮箱。"
            )
            
            await self.send_message_async(
                receive_id_type = "user_id",
                receive_id = user_id,
                content = welcome_text,
            )
        except Exception as error:
            print(f"[Magnus] Error in user welcome: {error}\n{traceback.format_exc()}")