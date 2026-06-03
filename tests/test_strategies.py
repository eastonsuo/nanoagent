"""strategies/ 单测 —— 三个默认策略的行为 + 两个 Hook 包装的接线。"""
from nanoagent.core import Context, Message, StopReason, ToolCall, ToolDecision
from nanoagent.strategies import (
    AllowAll,
    ContextHook,
    MaxTurnsStop,
    NoopContext,
    PermissionHook,
)


def test_max_turns_stop():
    s = MaxTurnsStop(3)
    assert s.should_stop(None, 0) is None
    assert s.should_stop(None, 2) is None
    assert s.should_stop(None, 3) is StopReason.MAX_TURNS
    assert s.should_stop(None, 9) is StopReason.MAX_TURNS


def test_noop_context_returns_all():
    msgs = [Message(role="user", content="a"), Message(role="assistant", content="b")]
    assert NoopContext().reduce(msgs, budget_tokens=10) is msgs


def test_allow_all():
    assert AllowAll().check(None, ToolCall("c", "f", {})).allowed is True


def test_context_hook_writes_view_not_log():
    ctx = Context()
    ctx.add(Message(role="system", content="s"))
    ctx.add(Message(role="user", content="u"))

    class KeepLast:
        def reduce(self, messages, budget_tokens):
            return messages[-1:]

    ContextHook(KeepLast()).before_model(ctx)
    assert ctx.view() == ctx.messages[-1:]   # view 被裁成最后一条
    assert len(ctx.messages) == 2            # 日志原封不动


def test_permission_hook_relays_decision():
    class DenyAll:
        def check(self, ctx, call):
            return ToolDecision(allowed=False, reason="blocked")

    d = PermissionHook(DenyAll()).before_tool(None, ToolCall("c", "f", {}))
    assert d.allowed is False and d.reason == "blocked"
