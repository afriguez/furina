from collections.abc import AsyncGenerator
import inspect
from dataclasses import asdict
import json
from typing import Any
import httpx

from app.models.schema import Message


class AIClient:
    def __init__(self, api_url: str, api_key: str, tool_registry: Any, tools: list[dict[str, Any]]) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.tools = tools
        self.registry = tool_registry

    async def post_messages_stream(self, messages: list[Message], max_tokens: int) -> AsyncGenerator[str, None]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        def merge_tool_call(old, new):
            merged = old.copy()
            merged_function = merged.get("function", {})
            new_function = new.get("function", {})

            if "name" in new_function:
                merged_function["name"] = new_function["name"]
            if "arguments" in new_function:
                merged_function["arguments"] = merged_function.get("arguments", "") + new_function["arguments"]

            merged["function"] = merged_function
            return merged

        def make_payload(msgs):
            return {
                "max_tokens": max_tokens,
                "model": "deepseek-chat",
                "stream": True,
                "messages": [asdict(m) if isinstance(m, Message) else m for m in msgs],
                "tools": self.tools if self.tools else None
            }

        async def stream_and_handle(msgs):
            tool_calls = []
            collecting_tool_calls = False

            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", self.api_url, headers=headers, json=make_payload(msgs)) as response:
                    async for line in response.aiter_lines():
                        if line:
                            if line.startswith("data: "):
                                line = line[6:]
                            if line.strip() == "[DONE]":
                                break

                            try:
                                chunk = json.loads(line)
                                choice = chunk["choices"][0]
                                delta = choice.get("delta", {})

                                if "tool_calls" in delta:
                                    collecting_tool_calls = True
                                    for tc in delta["tool_calls"]:
                                        index = tc["index"]
                                        if len(tool_calls) <= index:
                                            tool_calls.append(tc)
                                        else:
                                            tool_calls[index] = merge_tool_call(tool_calls[index], tc)

                                elif "content" in delta and not collecting_tool_calls:
                                    yield delta["content"]

                                if choice.get("finish_reason") == "tool_calls":
                                    tool_messages = []
                                    assistant_msg = {
                                        "role": "assistant",
                                        "tool_calls": tool_calls
                                    }
                                    msgs.append(assistant_msg)

                                    for call in tool_calls:
                                        fn_name = call["function"]["name"]
                                        arguments = json.loads(call["function"]["arguments"])
                                        call_id = call["id"]

                                        tool_output = await self.run_tool(fn_name, arguments)
                                        tool_messages.append({
                                            "role": "tool",
                                            "tool_call_id": call_id,
                                            "content": tool_output
                                        })

                                    msgs.extend(tool_messages)

                                    async for item in stream_and_handle(msgs):
                                        yield item
                                    return

                            except Exception as e:
                                print(f"[AIClient] [STREAM ERROR] {e}")

        async for item in stream_and_handle(messages):
            yield item

    async def post_messages(self, messages: list[Message], max_tokens: int) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "max_tokens": max_tokens,
            "model": "deepseek-chat",
            "messages": [
                asdict(m) if isinstance(m, Message) else m
                for m in messages
            ],
            "tools": self.tools if self.tools else None
        }

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=data)
                response_json = response.json()
                message_data = response_json["choices"][0]["message"]

                if "tool_calls" in message_data:
                    tool_messages = []
                    for tool_call in message_data["tool_calls"]:
                        function_name = tool_call["function"]["name"]
                        arguments = json.loads(tool_call["function"]["arguments"])
                        tool_call_id = tool_call["id"]

                        tool_result = await self.run_tool(function_name, arguments)

                        tool_messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": tool_result
                        })

                    new_messages = messages.copy()
                    new_messages.append(message_data)
                    new_messages.extend(tool_messages)

                    return await self.post_messages(new_messages, max_tokens)

                return message_data["content"]
            except httpx.RequestError as e:
                print("[AIClient] [ERROR] ", e)
                raise

    async def run_tool(self, name: str, args: dict[str, Any]) -> str:
        tool = self.registry.get(name)
        if not tool:
            return f"[AIClient] [Error] Tool '{name}' not found"

        if hasattr(tool, "run") and callable(tool.run):
            if inspect.iscoroutinefunction(tool.run):
                return await tool.run(args)
            return tool.run(args)

        return "[AIClient] [Error] Invalid tool"
