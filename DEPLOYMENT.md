# 🐳 Docker 部署指南

## 🚀 快速开始

### 1. 准备配置文件

```bash
# 复制示例配置文件
cp .env.example .env
cp api_keys.json.example api_keys.json
cp lark_api_keys.json.example lark_api_keys.json
cp mcp_servers_config.json.example mcp_servers_config.json

# 编辑配置文件，填入真实的密钥和配置
vim .env
vim api_keys.json
vim lark_api_keys.json
vim mcp_servers_config.json
```

### 2. 启动服务

```bash
# 拉取镜像并启动
docker compose pull
docker compose up -d

# 查看日志
docker compose logs -f
```

---

## ⚙️ GitHub Actions 自动构建

### 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下 Secrets：

**Settings → Secrets and variables → Actions → New repository secret**

| Secret 名称 | 说明 | 获取方式 |
|------------|------|---------|
| `DOCKER_USERNAME` | Docker Hub 用户名 | 你的 Docker Hub 用户名 |
| `DOCKER_PASSWORD` | Docker Hub 访问令牌 | Docker Hub → Account Settings → Security → New Access Token |

### 触发构建

#### 方式 1：创建版本标签（推荐）

```bash
# 创建版本标签自动触发构建
git tag v1.0.0
git push origin v1.0.0

# 自动生成以下镜像标签：
# - wjsoj/het-lark-bot:v1.0.0
# - wjsoj/het-lark-bot:1.0
# - wjsoj/het-lark-bot:1
# - wjsoj/het-lark-bot:latest
```

#### 方式 2：手动触发

1. 进入 GitHub 仓库 → **Actions**
2. 选择 **Build and Push Docker Image**
3. 点击 **Run workflow**
4. 选择分支并输入镜像标签（可选）
5. 点击 **Run workflow** 确认

---

## 📋 配置文件说明

### 必需的配置文件

| 文件 | 热重载 | 说明 |
|------|--------|------|
| `.env` | ❌ | Supabase 数据库配置 |
| `api_keys.json` | ❌ | AI 模型 API 密钥 |
| `lark_api_keys.json` | ❌ | 飞书机器人凭证 |
| `mcp_servers_config.json` | ❌ | MCP 服务器配置 |
| `configs/*.yaml` | ✅ | 机器人业务配置 |

### 配置示例

**.env**
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

**api_keys.json**
```json
{
  "Gemini-2.5-Pro": [
    {
      "api_key": "sk-your-key",
      "base_url": "https://api.example.com/v1",
      "model": "gemini-2.5-pro"
    }
  ]
}
```

**lark_api_keys.json**
```json
{
  "机器人名称": {
    "app_id": "cli_xxxxxx",
    "app_secret": "your-secret",
    "open_id": "ou_xxxxxx"
  }
}
```

---

## 🔄 日常操作

### 更新配置

**YAML 配置（热重载，无需重启）**
```bash
vim configs/pku_phy_fermion_config_251120_0900.yaml
# 保存后通过飞书触发重载命令
```

**JSON/ENV 配置（需要重启）**
```bash
vim api_keys.json
docker compose restart
```

### 更新镜像

```bash
# 拉取最新镜像
docker compose pull

# 重启服务
docker compose up -d
```

### 查看日志

```bash
# 实时查看日志
docker compose logs -f

# 查看最近 100 行
docker compose logs --tail=100

# 查看特定时间段
docker compose logs --since 1h
```

### 重启服务

```bash
docker compose restart
```

### 停止服务

```bash
docker compose down
```

---

## 🎯 完整部署流程

```bash
# 1. 准备配置
cp .env.example .env
cp api_keys.json.example api_keys.json
cp lark_api_keys.json.example lark_api_keys.json
cp mcp_servers_config.json.example mcp_servers_config.json

# 2. 编辑配置（填入真实的密钥）
vim .env
vim api_keys.json
vim lark_api_keys.json

# 3. 启动服务
docker compose pull
docker compose up -d

# 4. 验证运行
docker compose ps
docker compose logs -f
```
