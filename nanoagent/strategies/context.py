"""上下文策略：默认 NoopContext（不裁剪）+ 把任意 ContextStrategy 包成 Hook 的 ContextHook。"""
from __future__ import annotations

from nanoagent.core import BaseHook


class NoopContext:
    """默认上下文策略：不裁剪，view() 恒等于全量历史。"""

    def reduce(self, messages, budget_tokens):
        return messages


class ContextHook(BaseHook):
    """把一个 ContextStrategy「包」成 Hook：在 before_model 调 reduce、写投影（不碰日志）。

    v0.1 默认不启用（保持纯 ReAct）；显式 Agent(..., hooks=[ContextHook(strategy)]) 才介入。
    """

    def __init__(self, strategy, budget_tokens: int = 8000):
        self._s = strategy
        self._budget = budget_tokens

    def before_model(self, ctx) -> None:
        ctx.set_view(self._s.reduce(ctx.messages, self._budget))   # 只写 view 投影，绝不改 messages
