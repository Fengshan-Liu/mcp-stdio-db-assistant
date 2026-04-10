# MCP Stdio 数据库助手

[返回首页](./README.md) | [English](./README.en.md)

一个基于 FastAPI、OpenAI 兼容模型和 MCP stdio 的数据库助手示例项目。

项目包含两部分：

- `server.py`：通过 `FastMCP` 暴露数据库查询相关工具
- `client.py`：连接 stdio MCP 服务，并通过 FastAPI 提供 `/chat/` 接口

## 功能概览

- 启动本地 MCP stdio 服务
- 让大模型根据提示词选择并调用 MCP 工具
- 连接 MySQL 并查询表结构、条件数据和跨表搜索结果
- 提供一个简单的 HTTP 聊天接口和命令行测试客户端

## 项目结构

```text
.
├─ client.py
├─ server.py
├─ request.py
├─ MCP_Prompt.txt
├─ pyproject.toml
└─ .env.example
```

## 环境要求

- Python 3.13+
- MySQL
- OpenAI 兼容接口可用的 API Key 和 Base URL

## 安装

推荐使用 `uv`：

```bash
uv sync
```

如果你还没有环境文件，先复制一份：

```bash
copy .env.example .env
```

然后按实际情况填写：

```env
API_KEY=your_openai_api_key
BASE_URL=https://api.openai.com/v1
MODEL=gpt-4o-mini

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DEFAULT_DATABASE=app_db
```

## 启动

启动服务端：

```bash
uv run python client.py
```

服务启动后会监听：

```text
http://127.0.0.1:8000
```

## 调用接口

请求示例：

```bash
curl -X POST http://127.0.0.1:8000/chat/ ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"帮我查询订单表结构\"}"
```

也可以运行命令行客户端：

```bash
uv run python request.py
```

## 公开仓库前已处理

- `.env` 已加入忽略规则，不会被提交
- 虚拟环境和缓存目录已加入忽略规则
- 数据库连接配置改为从环境变量读取
- 示例配置改成了通用占位值

## 建议的 GitHub 仓库信息

- 仓库名：`mcp-stdio-db-assistant`
- 描述：`MCP stdio 数据库助手，基于 FastAPI 和 OpenAI 兼容工具调用`
