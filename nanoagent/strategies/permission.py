"""权限策略：默认 AllowAll（一律放行）+ 把任意 PermissionStrategy 包成 Hook 的 PermissionHook。"""
from __future__ import annotations

from nanoagent.core import BaseHook, ToolDecision


class AllowAll:
    """默认权限策略：一律放行。"""

    def check(self, ctx, call) -> ToolDecision:
        return ToolDecision(allowed=True)


class PermissionHook(BaseHook):
    """把一个 PermissionStrategy「包」成 Hook：在 before_tool 调 check、返回 ToolDecision。

    返回 allowed=False 是软拒绝：loop 只对该次调用回填 denial 消息、让模型换路，不终止整轮。
    """

    def __init__(self, strategy):
        self._s = strategy

    def before_tool(self, ctx, call) -> ToolDecision:
        return self._s.check(ctx, call)
