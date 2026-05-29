from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nanoagent.core.message import Message
from nanoagent.core.stop import StopReason


@dataclass
class Context:
    """一次 agent 运行的上下文。

    messages 是 append-only 事件日志（完整历史，策略不得删改）；
    view() 才是真正发给 LLM 的消息——v0.1 等于全量，v0.3 由上下文策略投影裁剪。
    """

    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)   # 跨轮累计 token（熔断/显示用量的唯一入口）
    summary: str | None = None                            # v0.1 占位：承载 v0.3 压缩摘要产物
    _rendered: list[Message] | None = field(default=None, repr=False)  # before_model 写入的裁剪视图

    def add(self, message: Message) -> None:
        self.messages.append(message)
        self._rendered = None             # 历史变了，作废旧投影，下次 view() 回落到全量

    def add_usage(self, usage: dict[str, int]) -> None:
        for k, v in usage.items():
            self.usage[k] = self.usage.get(k, 0) + v

    def view(self) -> list[Message]:
        """真正发给 LLM 的消息。v0.1：identity=全量历史。
        v0.3：before_model 里的上下文策略调用 set_view() 写入裁剪结果。"""
        return self._rendered if self._rendered is not None else self.messages

    def set_view(self, messages: list[Message]) -> None:
        """由 before_model 的上下文策略调用，提交本轮发给模型的投影（不改 messages）。"""
        self._rendered = messages


@dataclass
class AgentResult:
    """一次 agent 运行的最终结果。"""

    context: Context
    stop_reason: StopReason
    turns: int = 0                                        # 实际执行轮数（供 CLI 显示「N 轮」）
    usage: dict[str, int] = field(default_factory=dict)   # 跨轮累计 token（供 CLI 显示用量）

    @property
    def output(self) -> str:
        # 回扫最后一条「有内容的 assistant 文本」，避免在 MAX_TURNS（末条是工具结果）
        # 或权限拒绝（末条是 denial）时把非答复内容误当成输出。
        for m in reversed(self.context.messages):
            if m.role == "assistant" and m.content:
                return m.content
        return "" if self.stop_reason is StopReason.DONE else f"[未完成：{self.stop_reason.value}]"
