"""核心层 —— 数年不变的稳定部分。

本包不得 import 任何外层目录（strategies / tools / llm / memory / cli / api）：
依赖只能从外层指向 core（见 DESIGN §4.1、§8.1，CI 用 import-linter / grep 守）。
策略 Protocol（ContextStrategy / PermissionStrategy / StopStrategy）属契约、放本包；
它们的实现属 strategies/。
"""

from nanoagent.core.message import LLMResponse, Message, ToolCall, ToolResult
from nanoagent.core.stop import StopReason
from nanoagent.core.context import AgentResult, Context
from nanoagent.core.hooks import BaseHook, Hook, ToolDecision
from nanoagent.core.protocols import (
    ContextStrategy,
    LLMClient,
    MemoryBackend,
    PermissionStrategy,
    StopStrategy,
    Tool,
)
from nanoagent.core.errors import FatalError, NanoAgentError

__all__ = [
    # 数据结构
    "ToolCall",
    "ToolResult",
    "Message",
    "LLMResponse",
    "Context",
    "AgentResult",
    "StopReason",
    # Hook
    "ToolDecision",
    "Hook",
    "BaseHook",
    # 能力 / 策略契约
    "LLMClient",
    "Tool",
    "MemoryBackend",
    "ContextStrategy",
    "PermissionStrategy",
    "StopStrategy",
    # 异常
    "NanoAgentError",
    "FatalError",
]
