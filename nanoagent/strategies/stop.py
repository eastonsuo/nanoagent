"""停止策略：公开可配的 MaxTurnsStop（只看轮数）。

注意：core/loop.py 为不依赖 strategies（§8.1），自带一个等价的私有默认停止 `_MaxTurns`；
本类是公开、可显式传入 `AgentLoop(stop=MaxTurnsStop(n))` 或被 CompositeStop 组合的版本。
"""
from __future__ import annotations

from nanoagent.core import StopReason


class MaxTurnsStop:
    """实现 StopStrategy 协议（结构化，无需继承）。达 max_turns 即停。"""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns

    def should_stop(self, ctx, turn: int):
        return StopReason.MAX_TURNS if turn >= self.max_turns else None
