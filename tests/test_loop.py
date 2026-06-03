"""loop/ 集成测试 —— 用 EchoClient 脚本在不联网下跑通 ReAct 完整路径。

覆盖：DONE（无工具）/ 工具→回填→再推理→DONE / MAX_TURNS / before_tool 软拒绝 / 未知工具。
"""
from nanoagent.core import (
    AgentLoop,
    BaseHook,
    Context,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolDecision,
)
from nanoagent.llm import EchoClient
from nanoagent.tools import tool


@tool
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b


def _ctx(prompt="hi"):
    c = Context()
    c.add(Message(role="user", content=prompt))
    return c


def _resp(content="", calls=None):
    return LLMResponse(Message(role="assistant", content=content, tool_calls=calls or []))


def test_done_no_tool():
    r = AgentLoop(EchoClient(), tools=[]).run(_ctx("hello"))
    assert r.stop_reason is StopReason.DONE
    assert r.turns == 1
    assert r.output == "echo: hello"


def test_tool_then_done():
    script = [
        _resp(calls=[ToolCall("c1", "add", {"a": 2, "b": 3})]),
        _resp(content="结果是 5"),
    ]
    r = AgentLoop(EchoClient(script), tools=[add]).run(_ctx())
    assert r.stop_reason is StopReason.DONE
    assert r.output == "结果是 5"
    tool_msgs = [m for m in r.context.messages if m.role == "tool"]
    assert tool_msgs and tool_msgs[0].tool_result.content == "5"   # 工具结果回填


def test_max_turns():
    class AlwaysTool:
        def chat(self, messages, tools=None, **kw):
            return _resp(calls=[ToolCall("c", "add", {"a": 1, "b": 1})])

    r = AgentLoop(AlwaysTool(), tools=[add], max_turns=2).run(_ctx())
    assert r.stop_reason is StopReason.MAX_TURNS
    assert r.turns == 2


def test_before_tool_deny_is_soft():
    class DenyHook(BaseHook):
        def before_tool(self, ctx, call):
            return ToolDecision(allowed=False, reason="blocked")

    script = [_resp(calls=[ToolCall("c1", "add", {"a": 2, "b": 3})]), _resp(content="ok")]
    r = AgentLoop(EchoClient(script), tools=[add], hooks=[DenyHook()]).run(_ctx())
    tool_msgs = [m for m in r.context.messages if m.role == "tool"]
    assert tool_msgs[0].tool_result.is_error                 # 回填 denial、未真正执行
    assert "blocked" in tool_msgs[0].tool_result.content
    assert r.output == "ok"                                  # 软拒绝：模型换路后继续到 DONE


def test_unknown_tool_feeds_error():
    script = [_resp(calls=[ToolCall("c1", "nope", {})]), _resp(content="done")]
    r = AgentLoop(EchoClient(script), tools=[add]).run(_ctx())
    tool_msgs = [m for m in r.context.messages if m.role == "tool"]
    assert tool_msgs[0].tool_result.is_error
    assert "unknown tool" in tool_msgs[0].tool_result.content
