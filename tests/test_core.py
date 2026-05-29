"""core/ 层单测 —— 不依赖网络与 API key，`python -m pytest` 即可跑。

对应 v0.1-design.md §10 的「core」行：view 投影 / usage 累计 / output 回扫 /
BaseHook 默认放行 / 8 点 Hook / StopReason / 异常层级。
"""
from nanoagent.core import (
    AgentResult,
    BaseHook,
    Context,
    FatalError,
    Hook,
    Message,
    NanoAgentError,
    StopReason,
    ToolCall,
    ToolDecision,
    ToolResult,
)


def test_context_view_is_full_history_by_default():
    ctx = Context()
    ctx.add(Message(role="system", content="sys", pinned=True))
    ctx.add(Message(role="user", content="hi"))
    assert ctx.view() == ctx.messages              # v0.1：view == 全量 identity


def test_set_view_then_add_invalidates_projection():
    ctx = Context()
    ctx.add(Message(role="user", content="a"))
    ctx.add(Message(role="user", content="b"))
    ctx.set_view([ctx.messages[0]])
    assert len(ctx.view()) == 1                     # set_view 改投影
    ctx.add(Message(role="assistant", content="c"))
    assert ctx.view() == ctx.messages               # add 后旧投影作废、回落全量


def test_add_usage_accumulates_across_turns():
    ctx = Context()
    ctx.add_usage({"total_tokens": 10})
    ctx.add_usage({"total_tokens": 5, "prompt_tokens": 3})
    assert ctx.usage["total_tokens"] == 15
    assert ctx.usage["prompt_tokens"] == 3


def test_output_returns_last_assistant_text_skipping_tool():
    ctx = Context()
    ctx.add(Message(role="user", content="q"))
    ctx.add(Message(role="assistant", content="answer"))
    ctx.add(Message(role="tool", tool_result=ToolResult("c1", "tool-out")))
    r = AgentResult(ctx, StopReason.DONE, turns=1, usage=ctx.usage)
    assert r.output == "answer"                     # 回扫最后一条 assistant 文本，跳过末尾 tool


def test_output_placeholder_when_unfinished():
    ctx = Context()
    ctx.add(Message(role="user", content="q"))
    assert AgentResult(ctx, StopReason.MAX_TURNS).output == "[未完成：max_turns]"
    assert AgentResult(Context(), StopReason.DONE).output == ""


def test_base_hook_defaults_allow_tool():
    decision = BaseHook().before_tool(Context(), ToolCall("c1", "x", {}))
    assert isinstance(decision, ToolDecision)
    assert decision.allowed is True


def test_base_hook_observer_points_return_none():
    h, ctx = BaseHook(), Context()
    assert h.on_start(ctx) is None
    assert h.before_turn(ctx) is None
    assert h.before_compact(ctx) is None            # v0.1 声明但 loop 不 emit
    assert h.on_stop(ctx, StopReason.DONE) is None


def test_hook_protocol_has_exactly_eight_points():
    points = {m for m in dir(Hook) if not m.startswith("_")}
    assert points == {
        "on_start",
        "before_turn",
        "before_model",
        "after_model",
        "before_compact",
        "before_tool",
        "after_tool",
        "on_stop",
    }


def test_stop_reason_values():
    assert {r.value for r in StopReason} == {"done", "max_turns", "denied", "budget"}


def test_tool_decision_defaults():
    d = ToolDecision()
    assert d.allowed is True and d.reason == ""


def test_errors_hierarchy():
    assert issubclass(FatalError, NanoAgentError)
    assert issubclass(NanoAgentError, Exception)
