"""strategies/ —— core 三个策略 Protocol 的默认实现 + 把策略包成 Hook 的包装器。

三个默认实现都极简：v0.1 默认配置「不带 hook、纯 ReAct」就靠它们退化。
接线方式不同（DESIGN §5.4）：
  - ContextStrategy / PermissionStrategy 要被一个 Hook「包」起来才生效
    （ContextHook 在 before_model、PermissionHook 在 before_tool 调用）；
  - 停止策略（公开可配的 MaxTurnsStop）是 AgentLoop 的构造参数，不算 hook。
依赖方向：strategies 依赖 core（实现策略 Protocol、继承 BaseHook），core 不反向依赖。
"""
from nanoagent.strategies.context import ContextHook, NoopContext
from nanoagent.strategies.permission import AllowAll, PermissionHook
from nanoagent.strategies.stop import MaxTurnsStop

__all__ = ["NoopContext", "ContextHook", "AllowAll", "PermissionHook", "MaxTurnsStop"]
