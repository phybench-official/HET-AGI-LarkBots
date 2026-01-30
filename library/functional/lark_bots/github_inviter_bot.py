from ...fundamental import *
import aiohttp


__all__ = [
    "GithubInviterBot",
]


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
        
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()
        
        self._mention_me_text = f"@{self._config['name']}"
        
        # GitHub API 配置读取
        # 假定 config.json 中包含 github_token 和 github_org_name 字段
        self._github_base_url = "https://api.github.com"
        
        # 用于 HTTP 请求的 session，将在 lazy load 或首次使用时初始化
        self._http_session: Optional[aiohttp.ClientSession] = None
        
        # 用户映射缓存：Feishu OpenID -> Github Username
        # 不考虑内存泄漏，无限增长
        self._user_mapping: Dict[str, str] = {}


    async def _get_session(
        self,
    )-> aiohttp.ClientSession:
        
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        chat_type = parsed_message["chat_type"]
        is_thread_root = parsed_message["is_thread_root"]

        # 仅处理私聊消息
        if chat_type == "p2p":
            # 简单起见，只要是私聊根消息都处理，以便解析指令
            if is_thread_root:
                return True
        
        return False
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        # 即使是简单的指令 Bot，也遵循 ParallelThreadLarkBot 的上下文协议
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
        sender: Optional[str] = parsed_message["sender"]
        
        # 仅处理指令
        if text.startswith("/"):
            await self._handle_command(parsed_message)
        else:
            # 如果不是指令，提示用户
            await self.reply_message_async(
                response = "GithubInviter 仅接受指令操作。\n发送 /join_github <github_username> 申请加入组织。",
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
        
        # 鉴权：简单判定是否在管理员列表中
        is_admin = sender in self._config["admin_open_ids"]

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

        if command == "/join_github":
            # 任何人都可以执行，但角色不同
            if len(args) < 2:
                await self.reply_message_async("用法: /join_github <github_username>", message_id)
                return
            
            target_username = args[1]
            
            # 检查唯一绑定限制
            # sender_id 即飞书用户的 open_id
            if sender_id:
                if sender_id in self._user_mapping:
                    bound_username = self._user_mapping[sender_id]
                    # 如果尝试绑定的账号与已绑定的不一致 (忽略大小写)
                    if bound_username.lower() != target_username.lower():
                        await self.reply_message_async(
                            response = f"❌ 操作失败：您已绑定 GitHub 账号 '{bound_username}'，无法申请其他账号。\n如有疑问或需更换账号，请联系管理员。",
                            message_id = message_id
                        )
                        return
                    # 如果一致，允许重试 (pass)
                else:
                    # 首次绑定，记录映射
                    self._user_mapping[sender_id] = target_username

            # 逻辑：管理员邀请默认为 owner (admin)，普通用户邀请默认为 member (direct_member)
            invite_role = "admin" if is_admin else "direct_member"
            
            await self._invite_user_to_github(
                username = target_username, 
                role = invite_role, 
                message_id = message_id,
                inviter_is_admin = is_admin
            )
            return

        elif command == "/help":
            help_text = (
                "GithubInviter 指令列表：\n"
                "  /join_github <username>  申请加入组织 (需前往 GitHub 邮箱确认)\n"
                "  /help                    显示此帮助\n\n"
                "说明：每位用户仅限绑定一个 GitHub 账号；普通用户申请将作为成员加入，管理员操作将作为 Owner 加入。"
            )
            await self.reply_message_async(help_text, message_id)
            return
        
        else:
            await self.reply_message_async(f"未知指令: {command}", message_id)


    async def _invite_user_to_github(
        self,
        username: str,
        role: str,
        message_id: str,
        inviter_is_admin: bool,
    )-> None:
        
        try:
            github_token = self._config["github_token"]
            org_name = self._config["github_org_name"]
        except KeyError as e:
            await self.reply_message_async(f"配置错误：缺少 {str(e)}", message_id)
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
                    # 内部打印日志方便 debug，但不透传给用户
                    error_text = await resp.text()
                    print(f"[GithubInviterBot] Get User Failed: {resp.status} | {error_text}")
                    
                    await self.reply_message_async(
                        response = f"查找用户 '{username}' 失败。\n请确认 GitHub 用户名是否正确，如有疑问请联系管理员。",
                        message_id = message_id,
                    )
                    return
                user_data = await resp.json()
                user_id = user_data.get("id")
        except Exception as e:
            print(f"[GithubInviterBot] Network Error (Get User): {e}")
            await self.reply_message_async("网络请求出错，如有疑问请联系管理员。", message_id)
            return

        if not user_id:
            await self.reply_message_async(f"未找到用户 '{username}' 的 ID，请确认拼写。", message_id)
            return

        # 2. Send Invitation
        invite_url = f"{self._github_base_url}/orgs/{org_name}/invitations"
        
        # GitHub API Role Enum: 'admin' (Owner), 'direct_member' (Member)
        payload = {
            "invitee_id": user_id,
            "role": role, 
        }

        try:
            async with session.post(invite_url, headers=headers, json=payload) as resp:
                if resp.status == 201:
                    role_display = "管理员 (Owner)" if role == "admin" else "成员 (Member)"
                    await self.reply_message_async(
                        response = f"✅ 已向 {username} (ID: {user_id}) 发送 {role_display} 邀请。\n请检查您的 GitHub 注册邮箱或访问组织页面接受邀请。",
                        message_id = message_id,
                    )
                elif resp.status == 422:
                    # 422 通常意味着已经是成员或已邀请
                    # 这种情况下不需要看日志，直接提示业务含义即可
                    await self.reply_message_async(
                        response = f"⚠️ 邀请未发送：该用户已经是组织成员，或已有一个待处理的邀请。\n如有疑问请联系管理员。",
                        message_id = message_id,
                    )
                else:
                    # 其他错误 (403/404/500 等)
                    error_text = await resp.text()
                    print(f"[GithubInviterBot] Invite Failed: {resp.status} | {error_text}")
                    
                    await self.reply_message_async(
                        response = f"❌ 邀请请求失败 (Code: {resp.status})。\n如有疑问请联系管理员。",
                        message_id = message_id,
                    )
        except Exception as e:
            print(f"[GithubInviterBot] Network Error (Invite): {e}")
            await self.reply_message_async("网络请求出错，如有疑问请联系管理员。", message_id)
            return