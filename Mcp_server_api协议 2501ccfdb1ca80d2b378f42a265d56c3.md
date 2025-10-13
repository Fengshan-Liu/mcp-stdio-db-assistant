# Mcp_server_api协议

## 基本信息

请求方式：Post

请求地址：[http://172.23.215.195:5050/chat](http://172.23.215.195:5050/mcp)

## 请求

参数：

| 名称 | 类型 | 是否必填 | 示例值 | 描述 |
| --- | --- | --- | --- | --- |
| message | str | 是 | “连接数据库” | 与AI通信内容 |

示例：

```json
{
"message": "连接数据库"
}
```

## 回复

参数：

外层

| 名称 | 类型 | 是否必填 | 示例值 | 描述 |
| --- | --- | --- | --- | --- |
| message | string | 是 | ”n\n已成功连接到数据库scrb…“ | ai生成的消息 |
| tool_call_count | int | 否 | 1 | 本次请求触发的工具调用次数 |
| timestamp | string | 是 | 2025-08-15 10:38:32 | 返回时间 |
| tool_calls | array | 否 | [ {...} ] | 工具调用记录列表，每个元素代表一次工具执行 |

tool_calls

| 名称 | 类型 | 是否必填 | 示例值 | 描述 |
| --- | --- | --- | --- | --- |
| tool_calls.tool_name | int | 是 | connect_to_database_and_list_tables | 调用的工具名称 |
| tool_calls.arguments | string | 是 | {"database": "scrb"} | 调用工具时传入的参数对象 |
| tool_calls.arguments.database | string | 是 | scrb | 要连接的数据库名称 |
| tool_calls.result | array | 是 | [ { "type": "text", ... } ] | 工具执行后返回的结果内容（数组形式） |
| tool_calls.result.type | string | 是 | text | 结果内容的类型，如文本、图像等（当前为文本） |
| tool_calls.result.text | object | 是 | { "status": "success", ... } | 实际返回的结构化数据（原为字符串，已解析为 JSON 对象） |
| ool_calls.result.annotations | object/null | 否 | null | 附加的标注信息（当前为空） |
| tool_calls.result._meta | object/null | 否 | null | 内部元数据信息（调试或系统使用，当前为空） |
| tool_calls.successbool | boolean | 是 | true | 表示该工具调用是否成功执行 |
| tool_calls.error_messagestri | string/null | 否 | null | 若失败，返回的错误描述；成功则为 null |

tool_calls.result.text

| 名称 | 类型 | 是否必填 | 示例值 | 描述 |
| --- | --- | --- | --- | --- |
| status | string | 是 | success | 执行状态：`success`或`error` |
| message | string | 是 | 成功连接到数据库 'scrb'。 | 工具执行的具体结果描述 |
| available_tables | string | 是 | ["roaster", "test"] | 数据库中可用的数据表列表 |
| system_guidance | string | 是 | 请按照系统提示进行后续操作 | 系统给出的操作指引 |
| connection_info | string | 是 | 线程 26480 已连接到 scrb | 连接过程的技术信息，用于追踪会话 |

```json
{
  "message": "\n\n已成功连接到数据库scrb，并获取到可用表：roaster和test。请问需要进一步操作哪个表？例如查看表结构或查询数据。",
  "tool_calls": [
    {
      "tool_name": "connect_to_database_and_list_tables",
      "arguments": {
        "database": "scrb"
      },
      "result": [
        {
          "type": "text",
          "text": "{\n  \"status\": \"success\",\n  \"message\": \"成功连接到数据库 'scrb'。\",\n  \"available_tables\": [\n    \"roaster\",\n    \"test\"\n  ],\n  \"system_guidance\": \"请按照系统提示进行后续操作\",\n  \"connection_info\": \"线程 26480 已连接到 scrb\"\n}",
          "annotations": null,
          "_meta": null
        }
      ],
      "success": true,
      "error_message": null
    }
  ],
  "tool_call_count": 1,
  "timestamp": "2025-08-15 10:38:32"
}
```

## 服务端

LLM配置：在环境（.env）配置

```
Base_URL=
API_KEY=
MODEL=
```

Prompt：MCP_Prompt.txt