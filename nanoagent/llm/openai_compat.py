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

from nanoagent.core import LLMResponse, Message, NanoAgentError, ToolCall


def _safe(text):
    """去掉无法编码的孤立代理项（lone surrogate，如非 UTF-8 locale 下 input() 读坏的中文），
    避免 openai 请求 json 编码时抛 UnicodeEncodeError。干净字符串原样返回。"""
    if not isinstance(text, str):
        return text
    return text.encode("utf-8", "replace").decode("utf-8")


def _to_openai(m: Message) -> dict:
    """core Message → OpenAI message dict（内容统一过 _safe 净化）。"""
    if m.role == "tool":
        # tool 结果消息：必须带 tool_call_id 与前一条 assistant 的调用配对
        tr = m.tool_result
        return {
            "role": "tool",
            "tool_call_id": tr.call_id if tr else "",
            "content": _safe(tr.content) if tr else "",
        }
    if m.role == "assistant" and m.tool_calls:
        # 带工具调用的 assistant：arguments 序列化成 JSON 字符串
        return {
            "role": "assistant",
            "content": _safe(m.content) or None,
            "tool_calls": [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {
                        "name": c.name,
                        "arguments": _safe(json.dumps(c.arguments, ensure_ascii=False)),
                    },
                }
                for c in m.tool_calls
            ],
        }
    # system / user / 纯文本 assistant
    return {"role": m.role, "content": _safe(m.content)}


def _parse_tool_call(c) -> ToolCall:
    """单个 OpenAI tool_call → core ToolCall。

    arguments 非法（截断 / 缺引号 / 不是 JSON 对象）时不抛、不崩 loop：标记 parse_error、置空 arguments，
    交由 loop._invoke 喂回错误让模型自纠（对齐「未知工具名」的优雅降级，见 loop.py 的 _invoke）。
    DeepSeek / Kimi / 本地模型偶发非法工具参数 JSON，这条兜底很关键。
    """
    raw = c.function.arguments or "{}"
    try:
        args = json.loads(raw)
        if not isinstance(args, dict):                       # 合法 JSON 但非对象（如 "5" / "[1]"）不能当 kwargs
            raise ValueError("不是 JSON 对象")
    except (json.JSONDecodeError, ValueError) as e:
        return ToolCall(c.id, c.function.name, {},
                        parse_error=f"工具参数不是合法 JSON 对象（{e}）；请用合法 JSON 重发。")
    return ToolCall(c.id, c.function.name, args)


def _parse_response(resp) -> LLMResponse:
    """OpenAI 响应对象 → LLMResponse。tool_calls 只取 assistant 消息自带的那份。"""
    if not resp.choices:                                 # 空 choices（内容过滤 / 异常响应）：给清晰错误，别 IndexError 崩
        raise NanoAgentError("LLM 返回空 choices（无可用回复）——请检查模型 / 输入 / 内容审查设置。")
    choice = resp.choices[0].message
    msg = Message(
        role="assistant",
        content=choice.content or "",
        tool_calls=[_parse_tool_call(c) for c in (choice.tool_calls or [])],
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
