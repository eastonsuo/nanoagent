from __future__ import annotations

from typing import Any, Protocol

from nanoagent.core.context import Context
from nanoagent.core.hooks import ToolDecision
from nanoagent.core.message import LLMResponse, Message, ToolCall
from nanoagent.core.stop import StopReason


class LLMClient(Protocol):
    """LLM 客户端契约，统一 OpenAI / Anthropic / 本地模型。

    v0.1 只要求 chat（同步、整段返回）。流式（chat_stream）是 v0.2 的预留扩展：
    届时新增一个 StreamingLLMClient 协议、由 REPL 旁路直接调用，不改 core
    （见 DESIGN §14.3 REPL 流式输出）。
    """

    def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        ...


class Tool(Protocol):
    """工具契约。用户日常用 @tool 装饰器，框架内部按此协议处理。"""

    name: str
    description: str
    schema: dict          # OpenAI Function Calling 的 JSON Schema

    def __call__(self, **kwargs: Any) -> Any:
        ...


class MemoryBackend(Protocol):
    """Memory 契约，working / episodic / semantic 三层均符合此接口。"""

    def store(self, key: str, value: Any, metadata: dict | None = None) -> None:
        ...

    def retrieve(self, query: str, k: int = 5) -> list[Any]:
        ...

    def delete(self, key: str) -> None:
        ...


# —— 以下三个是「策略 Protocol」：契约属 core，实现属 strategies/（见 DESIGN §5.4 归属规则）。
#    core 依赖 core 内的协议不违反单向依赖。

class ContextStrategy(Protocol):
    """上下文管理策略，由 before_model hook 调用。

    只读 messages（完整日志）、产出裁剪后的 message 列表，再由 hook 写进
    ctx.set_view()——物理上无法破坏历史。产出列表须保持 tool_calls↔tool_result
    配对完整（删工具结果须连带删其 tool_call）。
    """

    def reduce(self, messages: list[Message], budget_tokens: int) -> list[Message]:
        ...


class PermissionStrategy(Protocol):
    """权限校验策略，由 before_tool hook 调用。"""

    def check(self, ctx: Context, call: ToolCall) -> ToolDecision:
        ...


class StopStrategy(Protocol):
    """停止条件策略，由 AgentLoop 每轮检查。"""

    def should_stop(self, ctx: Context, turn: int) -> StopReason | None:
        ...
