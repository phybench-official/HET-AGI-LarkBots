# HET-AGI-LarkBots

一个智能化的飞书（Lark/Feishu）机器人框架，集成 AI 模型和 MCP 工具，用于构建高性能的对话式应用。

## 特性

- **多模型支持**：集成 OpenAI、Gemini、Qwen 等主流 AI 模型
- **MCP 工具集成**：通过 MCP（Model Context Protocol）扩展工具能力（如 Mathematica、Wolfram Alpha）
- **并行消息处理**：基于多线程架构，支持高并发对话
- **飞书深度集成**：支持消息监听、文档操作、Webhook 触发
- **工作流配置**：通过 YAML 配置文件灵活定义机器人行为
- **数据库支持**：集成 Supabase 实现数据持久化

## 快速开始

### 依赖管理

本项目使用 [uv](https://github.com/astral-sh/uv) 管理依赖：

```bash
# 安装 uv（如果尚未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 安装依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate     # Windows
```

### 配置文件

复制示例配置文件并填入真实凭证：

```bash
cp .env.example .env
cp api_keys.json.example api_keys.json
cp lark_api_keys.json.example lark_api_keys.json
cp mcp_servers_config.json.example mcp_servers_config.json
```

### 启动机器人

```bash
python scripts/start_robots.py
```

## 部署

详细的 Docker 部署流程请参阅 **[DEPLOYMENT.md](./DEPLOYMENT.md)**

## 项目结构

```
HET-AGI-LarkBots/
├── library/                      # 核心代码库
│   ├── fundamental/              # 基础组件
│   │   ├── db_connector/         # 数据库连接器
│   │   ├── function_call_tools/  # 函数调用工具
│   │   ├── lark_tools/           # 飞书 API 封装
│   │   └── mcp_client/           # MCP 客户端
│   └── functional/               # 功能模块
│       └── lark_bots/            # 飞书机器人实现
│           ├── pku_phy_fermion_bot/  # 物理问题求解器
│           ├── problem_solver_bot.py # 通用问题求解器
│           └── parallel_thread_chat_bot.py  # 并行聊天基类
├── configs/                      # 配置文件（YAML）
├── scripts/                      # 启动脚本
├── documents/                    # 项目文档
├── .env                          # 环境变量（Supabase）
├── api_keys.json                 # AI 模型 API 密钥
└── mcp_servers_config.json       # MCP 服务器配置
```

## 配置说明

### 1. AI 模型配置（api_keys.json）

```json
{
  "Gemini-2.5-Pro": [
    {
      "api_key": "your-api-key",
      "base_url": "https://api.example.com/v1",
      "model": "gemini-2.5-pro"
    }
  ]
}
```

### 2. 工作流配置（configs/*.yaml）

每个机器人通过 YAML 文件定义行为，支持热重载。示例：

```yaml
name: 问题求解器
app_id: cli_xxxxxx
workflows:
  straight_forwarding:
    Gemini-2.5-Pro:
      model: Gemini-2.5-Pro-for-HET-AGI
      temperature: 0.7
      timeout: 300
```

## 核心组件

### 并行聊天机器人（ParallelThreadChatBot）

所有机器人的基类，提供：
- 多线程并发消息处理
- 自动消息解析和上下文管理
- 飞书 API 封装（发送消息、图片、文件）
- 配置热重载

### MCP 工具集成

通过 MCP 客户端调用外部工具：
- Mathematica 符号计算
- Wolfram Alpha 知识查询
- 自定义工具扩展

### 数据库连接器

集成 Supabase 实现：
- 对话历史存储
- 用户数据管理
- 问题集管理

## 示例机器人

### 1. 物理问题求解器（PkuPhyFermionBot）

专为物理学习设计的智能助手，支持：
- LaTeX 公式渲染
- Mathematica 符号计算
- 多工作流配置（直接回答/工具辅助）

### 2. 通用问题求解器（ProblemSolverBot）

通用对话机器人，适用于各类问答场景。

## 开发文档

- [部署指南](./DEPLOYMENT.md)

## 技术栈

- **Python 3.10+**
- **异步框架**：asyncio, uvloop
- **HTTP 客户端**：httpx, requests
- **飞书 SDK**：lark-oapi
- **AI 集成**：openai (兼容多模型)
- **数据库**：supabase
- **依赖管理**：uv