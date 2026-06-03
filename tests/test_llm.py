"""llm/ 单测 —— 全程不联网、不需要安装 openai。

双向转换 `_to_openai` / `_parse_response` 是模块级纯函数（openai 仅在
OpenAICompatClient.__init__ 内懒加载），故可脱离 openai 与网络逐 case 断言。
EchoClient 的脚本能力是后续 loop 多轮路径单测的基石。
"""
import json
from types import SimpleNamespace as NS

from nanoagent.core import LLMResponse, Message, ToolCall, ToolResult
from nanoagent.llm import EchoClient
from nanoagent.llm.openai_compat import _parse_response, _to_openai


def test_echo_default():
    r = EchoClient().chat([Message(role="user", content="hi")])
    assert isinstance(r, LLMResponse)
    assert r.message.role == "assistant"
    assert r.message.content == "echo: hi"
    assert r.usage["total_tokens"] == 1


def test_echo_script_in_order_then_fallback():
    scripted = [
        LLMResponse(Message(role="assistant", tool_calls=[ToolCall("c1", "f", {})])),
        LLMResponse(Message(role="assistant", content="done")),
    ]
    c = EchoClient(script=scripted)
    assert c.chat([Message(role="user", content="x")]).message.tool_calls[0].name == "f"
    assert c.chat([Message(role="user", content="x")]).message.content == "done"
    # 脚本耗尽后回落到默认 echo
    assert c.chat([Message(role="user", content="last")]).message.content == "echo: last"


def test_to_openai_user():
    assert _to_openai(Message(role="user", content="hello")) == {"role": "user", "content": "hello"}


def test_to_openai_assistant_tool_calls():
    d = _to_openai(Message(role="assistant", content="",
                           tool_calls=[ToolCall("call_1", "read_file", {"path": "a.txt"})]))
    assert d["role"] == "assistant"
    tc = d["tool_calls"][0]
    assert tc["id"] == "call_1" and tc["type"] == "function"
    assert tc["function"]["name"] == "read_file"
    assert json.loads(tc["function"]["arguments"]) == {"path": "a.txt"}


def test_to_openai_tool_message_pairs_call_id():
    d = _to_openai(Message(role="tool", tool_result=ToolResult(call_id="call_1", content="42")))
    assert d == {"role": "tool", "tool_call_id": "call_1", "content": "42"}


def test_to_openai_sanitizes_lone_surrogate():
    # 非 UTF-8 locale 下 input() 读坏的中文会带孤立代理项；_to_openai 应净化、使 content 可编码（不崩）
    d = _to_openai(Message(role="user", content="查\udce8询"))
    d["content"].encode("utf-8")   # 不抛 UnicodeEncodeError 即净化成功


def test_parse_response_text():
    resp = NS(choices=[NS(message=NS(content="hi", tool_calls=None))],
              usage=NS(prompt_tokens=3, completion_tokens=2, total_tokens=5))
    r = _parse_response(resp)
    assert r.message.role == "assistant"
    assert r.message.content == "hi"
    assert r.message.tool_calls == []
    assert r.usage == {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


def test_parse_response_tool_calls():
    tc = NS(id="call_1", function=NS(name="read_file", arguments='{"path": "a"}'))
    resp = NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))],
              usage=NS(prompt_tokens=1, completion_tokens=1, total_tokens=2))
    r = _parse_response(resp)
    assert r.message.content == ""                       # None → ""
    assert r.message.tool_calls[0].id == "call_1"
    assert r.message.tool_calls[0].name == "read_file"
    assert r.message.tool_calls[0].arguments == {"path": "a"}
