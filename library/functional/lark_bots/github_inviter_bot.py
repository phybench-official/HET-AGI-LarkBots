from ...fundamental import *
# from .workflows import *
from ...fundamental.lark_tools._lark_sdk import P2ContactUserCreatedV3
import aiohttp

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
        
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()
        
        self._mention_me_text = f"@{self._config['name']}"
        
        # GitHub API 配置读取
        # 假定 config.json 中包含 github_token 和 github_org_name 字段
        self._github_base_url = "https://api.github.com"
        
        # 用于 HTTP 请求的 session，将在 lazy load 或首次使用时初始化
        self._http_session: Optional[aiohttp.ClientSession] = None


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
                response = "GithubInviter 仅接受指令操作。\n发送 /join_github <github_username> 以邀请用户。",
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
            if not is_admin:
                await self.reply_message_async("错误: 权限不足 (EACCES)", message_id)
                return
            
            if len(args) < 2:
                await self.reply_message_async("用法: /join_github <github_username>", message_id)
                return
            
            target_username = args[1]
            await self._invite_user_to_github(target_username, message_id)
            return

        elif command == "/help":
            help_text = (
                "GithubInviter 指令列表：\n"
                "  /join_github <username>  邀请用户加入组织\n"
                "  /help                    显示此帮助"
            )
            await self.reply_message_async(help_text, message_id)
            return
        
        else:
            await self.reply_message_async(f"未知指令: {command}", message_id)


    async def _invite_user_to_github(
        self,
        username: str,
        message_id: str,
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
        # GitHub API 邀请接口通常推荐使用 ID，虽然部分接口支持 email，但 username 需要转换
        user_url = f"{self._github_base_url}/users/{username}"
        async with session.get(user_url, headers=headers) as resp:
            if resp.status != 200:
                error_msg = await resp.text()
                await self.reply_message_async(
                    response = f"查找用户 '{username}' 失败 (HTTP {resp.status})。\nGitHub 返回: {error_msg}",
                    message_id = message_id,
                )
                return
            user_data = await resp.json()
            user_id = user_data.get("id")

        if not user_id:
            await self.reply_message_async(f"未找到用户 '{username}' 的 ID。", message_id)
            return

        # 2. Send Invitation
        invite_url = f"{self._github_base_url}/orgs/{org_name}/invitations"
        payload = {
            "invitee_id": user_id,
            "role": "direct_member", 
        }

        async with session.post(invite_url, headers=headers, json=payload) as resp:
            if resp.status == 201:
                await self.reply_message_async(
                    response = f"✅ 成功邀请用户 {username} (ID: {user_id}) 加入组织 {org_name}。",
                    message_id = message_id,
                )
            elif resp.status == 422:
                # 常见错误：用户已经在组织中
                raw_resp = await resp.text()
                await self.reply_message_async(
                    response = f"⚠️ 邀请失败：用户可能已在组织中或有待处理的邀请。\nGitHub 返回: {raw_resp}",
                    message_id = message_id,
                )
            else:
                error_msg = await resp.text()
                await self.reply_message_async(
                    response = f"❌ 邀请请求失败 (HTTP {resp.status})。\nGitHub 返回: {error_msg}",
                    message_id = message_id,
                )