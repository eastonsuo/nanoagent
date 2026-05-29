from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from nanoagent.core.context import Context
from nanoagent.core.message import LLMResponse, ToolCall, ToolResult
from nanoagent.core.stop import StopReason


@dataclass
class ToolDecision:
    """before_tool 的返回：是否放行一次工具调用。"""

    allowed: bool = True
    reason: str = ""


class Hook(Protocol):
    """Agent 生命周期钩子。所有 harness 能力都经此注入。

    8 个生命周期点中只有 before_tool 有返回值（ToolDecision），因为只有它需要
    影响核心循环的控制流；其余 7 个是纯观察 / 副作用点。

    on_start 在整个 run 起始 emit 一次；before_turn 每轮 emit。
    before_compact 为 v0.3 上下文压缩预留：v0.1 的 AgentLoop 不 emit 它（无压缩），
    与 DESIGN §5.1.1 的占位字段同属「v0.1 声明、暂不驱动」。
    """

    def on_start(self, ctx: Context) -> None:
        """整个 run 开始时（仅一次）。"""

    def before_turn(self, ctx: Context) -> None:
        """每一轮 turn 开始前。"""

    def before_model(self, ctx: Context) -> None:
        """调用 LLM 前。上下文管理策略在此介入（set_view）。"""

    def after_model(self, ctx: Context, response: LLMResponse) -> None:
        """LLM 返回后。"""

    def before_compact(self, ctx: Context) -> None:
        """上下文压缩前（v0.3 启用；v0.1 不 emit）。"""

    def before_tool(self, ctx: Context, call: ToolCall) -> ToolDecision:
        """执行工具前。权限校验策略在此介入，可拒绝调用。"""

    def after_tool(self, ctx: Context, call: ToolCall, result: ToolResult) -> None:
        """工具执行后。"""

    def on_stop(self, ctx: Context, reason: StopReason) -> None:
        """循环结束时。"""


class BaseHook:
    """8 个生命周期点的空实现。使用者继承它，只覆盖关心的点。"""

    def on_start(self, ctx: Context) -> None: ...
    def before_turn(self, ctx: Context) -> None: ...
    def before_model(self, ctx: Context) -> None: ...
    def after_model(self, ctx: Context, response: LLMResponse) -> None: ...
    def before_compact(self, ctx: Context) -> None: ...
    def before_tool(self, ctx: Context, call: ToolCall) -> ToolDecision:
        return ToolDecision(allowed=True)   # 默认放行，对齐 v0.1 allow-all
    def after_tool(self, ctx: Context, call: ToolCall, result: ToolResult) -> None: ...
    def on_stop(self, ctx: Context, reason: StopReason) -> None: ...
