"""OpenAICompatClient —— 包官方 openai SDK，在 core Message 与 OpenAI message dict 间双向翻译。

兼容任何 OpenAI 风格接口（DeepSeek / Kimi / vLLM / Ollama 等），由 base_url 区分。
`resolve_model`（读 API key、选 endpoint）在 api 层，不在这里——本客户端只收已解析的 model 名与可选 base_url。

两个易踩的坑（v0.1-design §5.1）：
① tool_calls 的唯一权威源是 assistant 消息自带的 tool_calls；
② tool 消息必须带 tool_call_id 且与前一条 assistant 的某个 tool_calls[].id 配对，否则下一轮 400。

`_to_openai` / `_parse_response` 是模块级纯函数：不触发 openai import，可脱离网络逐 case 单测。
"""
from __future__ import annotations

import json

from nanoagent.core import LLMResponse, Message, ToolCall


def _to_openai(m: Message) -> dict:
    """core Message → OpenAI message dict。"""
    if m.role == "tool":
        # tool 结果消息：必须带 tool_call_id 与前一条 assistant 的调用配对
        tr = m.tool_result
        return {
            "role": "tool",
            "tool_call_id": tr.call_id if tr else "",
            "content": tr.content if tr else "",
        }
    if m.role == "assistant" and m.tool_calls:
        # 带工具调用的 assistant：arguments 序列化成 JSON 字符串
        return {
            "role": "assistant",
            "content": m.content or None,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.name,
                        "arguments": json.dumps(c.arguments, ensure_ascii=False),
                    },
                }
                for c in m.tool_calls
            ],
        }
    # system / user / 纯文本 assistant
    return {"role": m.role, "content": m.content}


def _parse_response(resp) -> LLMResponse:
    """OpenAI 响应对象 → LLMResponse。tool_calls 只取 assistant 消息自带的那份。"""
    choice = resp.choices[0].message
    msg = Message(
        role="assistant",
        content=choice.content or "",
        tool_calls=[
            ToolCall(c.id, c.function.name, json.loads(c.function.arguments or "{}"))
            for c in (choice.tool_calls or [])
        ],
    )
    u = getattr(resp, "usage", None)
    usage = (
        {
            "prompt_tokens": u.prompt_tokens,
            "completion_tokens": u.completion_tokens,
            "total_tokens": u.total_tokens,
        }
        if u
        else {}
    )
    return LLMResponse(message=msg, usage=usage)


class OpenAICompatClient:
    """实现 LLMClient 协议（结构化，无需继承）。openai SDK 在此懒加载。

    兼容任何 OpenAI 风格接口，换 model + base_url 即可。例 ：
      - OpenAI       ：OpenAICompatClient("gpt-4o-mini")
      - **DeepSeek**  ：OpenAICompatClient("deepseek-chat", base_url="https://api.deepseek.com")
      - Kimi / vLLM / Ollama 同理（各自的 base_url）。
    api_key 缺省由 SDK 读 OPENAI_API_KEY；CLI 还支持用 OPENAI_BASE_URL 环境变量切到 DeepSeek 等端点。
    """

    def __init__(self, model: str, base_url: str | None = None, api_key: str | None = None):
        from openai import OpenAI  # 重依赖懒加载：仅真正用真实客户端时才需要 openai

        self.model = model
        opts: dict = {}
        if base_url:
            opts["base_url"] = base_url
        if api_key:
            opts["api_key"] = api_key
        self._client = OpenAI(**opts)   # api_key 缺省时由 SDK 读 OPENAI_API_KEY

    def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[_to_openai(m) for m in messages],
            tools=[t.schema for t in tools] if tools else None,
            **kwargs,
        )
        return _parse_response(resp)
