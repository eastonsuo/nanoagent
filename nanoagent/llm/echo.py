"""EchoClient —— 测试基石：不联网，按预设脚本返回 LLMResponse。

预设脚本可造出「第一轮返回带 tool_calls 的 assistant、第二轮返回纯文本」的序列，
从而在不联网下测出 loop 的「调工具 → 回填 → 再推理 → DONE」完整路径（DESIGN §5.2 / v0.1-design §5.2）。
"""
from __future__ import annotations

from nanoagent.core import LLMResponse, Message


class EchoClient:
    """实现 LLMClient 协议（结构化，无需继承）。不联网。"""

    def __init__(self, script: list[LLMResponse] | None = None):
        self._script = list(script or [])     # 预设的若干轮响应，按序弹出

    def chat(self, messages, tools=None, **kwargs) -> LLMResponse:
        if self._script:
            return self._script.pop(0)         # 有脚本：按序返回预设响应
        last = messages[-1].content if messages else ""
        return LLMResponse(
            message=Message(role="assistant", content=f"echo: {last}"),
            usage={"total_tokens": 1},
        )
