from __future__ import annotations

from enum import Enum


class StopReason(Enum):
    """agent loop 的退出原因（DESIGN §2.2、§5.1）。

    只有 DONE 表示「任务自然完成」；其余三个都是「被迫终止」。
    DONE 在模型不再调工具时产生；MAX_TURNS / DENIED / BUDGET 统一经每轮
    轮首的 StopStrategy.should_stop 产生。
    """

    DONE = "done"            # 模型不再调工具，任务完成
    MAX_TURNS = "max_turns"  # 达到最大轮数
    DENIED = "denied"        # 被权限策略终止
    BUDGET = "budget"        # 被熔断器终止
