"""AgentLoop —— 全项目的心脏：把 core 契约编排成约 30 行的 ReAct 循环。

主体只含 ReAct 主干（推理 → 工具 → 回填），不含任何具体策略代码——harness 行为都在
`_emit` / `_gate` / `stop.should_stop` 背后（这条定性规则是硬的，「~30 行」是它的标尺）。

依赖防线（§8.1）：本模块属 core，只 import core 自身的子模块，绝不 import strategies/llm/tools/...。
默认停止用 core 内置的 `_MaxTurns`（公开可配的 `MaxTurnsStop` 在 strategies/，由 api 或用户显式传入），
以免 core 反向依赖 strategies。
"""
from __future__ import annotations

import json

from nanoagent.core.context import AgentResult, Context
from nanoagent.core.errors import FatalError
from nanoagent.core.hooks import ToolDecision
from nanoagent.core.message import Message, ToolCall, ToolResult
from nanoagent.core.stop import StopReason


class _MaxTurns:
    """core 内置默认停止：达 max_turns 即停。等价于 strategies.MaxTurnsStop，
    放 core 是为了让 AgentLoop 不依赖 strategies（§8.1）。"""

    def __init__(self, max_turns: int):
        self.max_turns = max_turns

    def should_stop(self, ctx: Context, turn: int):
        return StopReason.MAX_TURNS if turn >= self.max_turns else None


def _stringify(value) -> str:
    """工具返回值 → str（无损：str 原样、其余 json.dumps 兜底）。core 绝不截断（那是 v0.3 ContextStrategy 的事）。"""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)


def _denial_message(call: ToolCall, reason: str) -> Message:
    """被拒工具调用 → role=tool 且 call_id 配对的消息，保证 OpenAI tool_call/tool 配对完整（否则下一轮 400）。"""
    return Message(
        role="tool",
        tool_result=ToolResult(call.id, content=f"调用被拒绝：{reason}", is_error=True),
    )


class AgentLoop:
    """约 30 行的 ReAct 核心循环。无状态：状态全在传入的 Context 里。"""

    def __init__(self, llm, tools, hooks=None, stop=None, max_turns: int = 20):
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.hooks = hooks or []
        self.stop = stop or _MaxTurns(max_turns)      # 默认 max-turns；保持 noop 纯 ReAct

    def run(self, ctx: Context) -> AgentResult:
        self._emit("on_start", ctx)                          # 整个 run 起始一次
        turn = 0
        while True:
            reason = self.stop.should_stop(ctx, turn)        # 轮次 / 预算 / 成本统一在此判定
            if reason is not None:
                self._emit("on_stop", ctx, reason)
                return AgentResult(ctx, reason, turn, ctx.usage)

            self._emit("before_turn", ctx)                   # 每一轮 turn 开始
            self._emit("before_model", ctx)                  # 上下文策略在此 set_view()
            response = self.llm.chat(ctx.view(), tools=list(self.tools.values()))
            self._emit("after_model", ctx, response)
            ctx.add(response.message)
            ctx.add_usage(response.usage)

            if not response.message.tool_calls:              # 终态：模型不再调工具
                self._emit("on_stop", ctx, StopReason.DONE)
                return AgentResult(ctx, StopReason.DONE, turn + 1, ctx.usage)

            for call in response.message.tool_calls:
                decision = self._gate(ctx, call)             # before_tool：软拒绝 → continue
                if not decision.allowed:
                    ctx.add(_denial_message(call, decision.reason))
                    continue
                result = self._invoke(call)
                self._emit("after_tool", ctx, call, result)
                ctx.add(Message(role="tool", tool_result=result))
            turn += 1

    # —— 辅助函数（不铺进主体；harness 行为都在这背后）——

    def _emit(self, point: str, *args) -> None:
        for h in self.hooks:
            getattr(h, point)(*args)                         # 调每个 hook 的同名方法；v0.1 不吞异常，直接上抛

    def _gate(self, ctx: Context, call: ToolCall) -> ToolDecision:
        for h in self.hooks:                                 # deny-first：第一个拒绝者说了算
            d = h.before_tool(ctx, call)
            if d is not None and not d.allowed:
                return d
        return ToolDecision(allowed=True)                    # 无 hook / 全放行 → 默认放行

    def _invoke(self, call: ToolCall) -> ToolResult:
        if call.name not in self.tools:                      # 模型可能幻觉工具名 → 喂回错误而非抛
            return ToolResult(call.id, content=f"unknown tool: {call.name}", is_error=True)
        try:
            value = self.tools[call.name](**call.arguments)
            return ToolResult(call.id, content=_stringify(value))
        except FatalError:
            raise                                            # 框架级致命错误：上抛，不喂回
        except Exception as e:                                # 工具业务异常：转 is_error 喂回模型 self-heal
            return ToolResult(call.id, content=f"{type(e).__name__}: {e}", is_error=True)
