from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """模型发起的一次工具调用请求。"""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """一次工具执行的结果。"""

    call_id: str
    content: str          # 工具返回值经字符串化后的内容（core 只做无损 str()，不截断）
    is_error: bool = False
    raw_bytes: int = 0    # v0.1 占位：content 字节数，供 v0.3 策略判断是否需清理
    elided: bool = False  # v0.1 占位：v0.3 上下文策略可据此把旧工具结果剔出视图（数据仍留 messages）


@dataclass
class Message:
    """对话中的一条消息。一旦 add 进 Context 即视为不可变事件，策略不得删改它。"""

    role: str             # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_result: ToolResult | None = None
    # ↓ 以下为 v0.3 上下文工程预留的「抓手」，v0.1 仅填充、绝不消费（见 DESIGN §5.1.1）
    pinned: bool = False               # True=裁剪策略不得丢弃（如 system / 关键决策）
    ephemeral: bool = False            # True=可被工具结果清理策略优先移出视图
    token_estimate: int | None = None  # 由上下文策略按需回填，供按预算截断/熔断判定


@dataclass
class LLMResponse:
    """一次 LLM 调用的返回。assistant 消息自带的 tool_calls 即本轮工具调用（唯一权威源）。"""

    message: Message
    usage: dict[str, int] = field(default_factory=dict)   # 本轮 token 统计
