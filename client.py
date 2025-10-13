import asyncio
from typing import Optional, List, Dict, Any
from contextlib import AsyncExitStack
import json
import re
from openai import OpenAI
import xml.etree.ElementTree as etree
from datetime import datetime

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fastapi import FastAPI
from pydantic import BaseModel  
import uvicorn

from dotenv import load_dotenv
import os

from loguru import logger
load_dotenv(encoding='utf-8-sig')

# 全局变量存储客户端实例
mcp_client_instance = None

class ToolCallResult(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Any
    success: bool
    error_message: Optional[str] = None

class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
        # 环境变量配置
        self.API_KEY = os.getenv("API_KEY")
        self.BASE_URL = os.getenv("BASE_URL")
        self.MODEL = os.getenv("MODEL")
        
        # 创建LLM client
        self.client = OpenAI(api_key=self.API_KEY, base_url=self.BASE_URL)
        
        # 存储历史消息
        self.messages = []
        
        # 最大工具调用次数
        self.max_tool_calls = 10
        
        # 读取提示词模板
        with open("./MCP_Prompt.txt", "r", encoding="utf-8") as file:
            self.system_prompt = file.read()

    async def connect_to_stdio_server(self, mcp_name, command: str, args: list[str]):
        """连接到MCP服务器"""
        server_params = StdioServerParameters(command=command, args=args, env={})

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        
        # 将MCP信息添加到system_prompt
        response = await self.session.list_tools()
        available_tools = [
            '##' + mcp_name + '\n### Available Tools\n- ' + tool.name + "\n" + tool.description + "\n" + json.dumps(tool.inputSchema) 
            for tool in response.tools
        ]
        self.system_prompt = self.system_prompt.replace("<$MCP_INFO$>", "\n".join(available_tools) + "\n<$MCP_INFO$>")
        tools = response.tools
        print(f"Successfully connected to {mcp_name} server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> tuple[str, List[ToolCallResult]]:
        """处理查询，返回最终回答和工具调用结果列表"""
        if not any(msg["role"] == "system" for msg in self.messages):
            self.messages.append({
                "role": "system",
                "content": self.system_prompt
            })
            
        self.messages.append({
            "role": "user",
            "content": query
        })
       
        tool_call_count = 0
        content = None
        tool_call_results = []  # 存储所有工具调用结果
        
        while tool_call_count < self.max_tool_calls:
            try:
                # LLM API调用
                response = self.client.chat.completions.create(
                    model=self.MODEL,
                    max_tokens=4096,
                    messages=self.messages,
                )
                
                content = response.choices[0].message.content
                
                # 检查是否需要调用工具
                if '<use_mcp_tool>' not in content:
                    return content, tool_call_results
                
                # 解析并执行工具调用
                server_name, tool_name, tool_args = self.parse_tool_string(content)
                
                try:
                    result = await self.session.call_tool(tool_name, tool_args)
                    
                    # 记录成功的工具调用
                    tool_call_results.append(ToolCallResult(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=result.content,
                        success=True
                    ))
                    
                    # 将助手回复和工具结果添加到消息历史
                    self.messages.append({"role": "assistant", "content": content})
                    self.messages.append({"role": "user", "content": f"[工具 {tool_name} 返回结果: {result.content}]"})
                    
                except Exception as tool_error:
                    # 记录失败的工具调用
                    tool_call_results.append(ToolCallResult(
                        tool_name=tool_name,
                        arguments=tool_args,
                        result=None,
                        success=False,
                        error_message=str(tool_error)
                    ))
                    
                    error_msg = f"工具调用失败: {str(tool_error)}"
                    self.messages.append({"role": "assistant", "content": content})
                    self.messages.append({"role": "user", "content": f"[错误: {error_msg}]"})
                
                tool_call_count += 1
                
            except Exception as e:
                error_msg = f"工具调用准备失败: {str(e)}"
                self.messages.append({"role": "assistant", "content": content if content else "工具调用准备失败"})
                self.messages.append({"role": "user", "content": f"[错误: {error_msg}]"})
                tool_call_count += 1
        
        # 达到最大工具调用次数，生成最终回复
        try:
            final_response = self.client.chat.completions.create(
                model=self.MODEL,
                max_tokens=4096,
                messages=self.messages + [{"role": "user", "content": "请基于以上的工具调用结果，给出最终的答案和总结。不要再调用工具。"}],
            )
            return final_response.choices[0].message.content, tool_call_results
        except Exception as e:
            return f"生成最终回复时出错: {str(e)}", tool_call_results
    
    def parse_tool_string(self, tool_string: str) -> tuple[str, str, dict]:
        """解析工具调用字符串"""
        try:
            tool_matches = re.findall("(<use_mcp_tool>.*?</use_mcp_tool>)", tool_string, re.S)
            if not tool_matches:
                raise ValueError("未找到工具调用标签")
            
            tool_xml = tool_matches[0]
            root = etree.fromstring(tool_xml)
            
            server_name = root.find('server_name').text
            tool_name = root.find('tool_name').text
            tool_args = json.loads(root.find('arguments').text)
            
            return server_name, tool_name, tool_args
        except Exception as e:
            raise ValueError(f"解析工具调用字符串失败: {e}")

    async def cleanup(self):
        """清理资源"""
        await self.exit_stack.aclose()

# FastAPI 应用
app = FastAPI()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    message: str
    tool_calls: List[ToolCallResult] = []
    tool_call_count: int = 0
    timestamp: str  # 响应时间

@app.post("/chat/", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """聊天接口"""
    global mcp_client_instance
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if mcp_client_instance is None:
        return ChatResponse(
            message="MCP客户端未初始化",
            tool_calls=[],
            tool_call_count=0,
            timestamp=current_time
        )
    
    try:
        response_message, tool_call_results = await mcp_client_instance.process_query(request.message)
        return ChatResponse(
            message=response_message,
            tool_calls=tool_call_results,
            tool_call_count=len(tool_call_results),
            timestamp=current_time
        )
    except Exception as e:
        return ChatResponse(
            message=f"处理请求时出错: {str(e)}",
            tool_calls=[],
            tool_call_count=0,
            timestamp=current_time
        )

async def init_mcp_client():
    """初始化MCP客户端"""
    global mcp_client_instance
    
    mcp_client_instance = MCPClient()
    await mcp_client_instance.connect_to_stdio_server('server', 'python', ['server.py'])
    logger.info("MCP客户端初始化完成")

async def main():
    """主函数"""
    # 初始化MCP客户端
    await init_mcp_client()
    
    # 启动FastAPI服务器
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    finally:
        if mcp_client_instance:
            await mcp_client_instance.cleanup()

if __name__ == "__main__":
    asyncio.run(main())