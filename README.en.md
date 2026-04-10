# MCP Stdio DB Assistant

[Home](./README.md) | [中文](./README.zh-CN.md)

An example database assistant project built with FastAPI, OpenAI-compatible models, and MCP stdio.

The repository includes:

- `server.py`: exposes database query tools through `FastMCP`
- `client.py`: connects to the stdio MCP server and provides a FastAPI `/chat/` endpoint

## Features

- Starts a local MCP stdio server
- Lets an LLM choose and call MCP tools from prompt instructions
- Connects to MySQL for schema lookup, filtered queries, and cross-table search
- Provides a simple HTTP chat API and a lightweight CLI client

## Project Structure

```text
.
├─ client.py
├─ server.py
├─ request.py
├─ MCP_Prompt.txt
├─ pyproject.toml
└─ .env.example
```

## Requirements

- Python 3.13+
- MySQL
- An API key and base URL for an OpenAI-compatible endpoint

## Installation

Using `uv` is recommended:

```bash
uv sync
```

If you do not have an environment file yet, create one first:

```bash
copy .env.example .env
```

Then fill in your actual values:

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

## Run

Start the service:

```bash
uv run python client.py
```

The API will listen on:

```text
http://127.0.0.1:8000
```

## API Example

```bash
curl -X POST http://127.0.0.1:8000/chat/ ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Show me the schema for the orders table\"}"
```

You can also run the CLI client:

```bash
uv run python request.py
```

## GitHub Repository Recommendation

- Repository name: `mcp-stdio-db-assistant`
- Description: `MCP stdio database assistant with FastAPI and OpenAI-compatible tool calling`
