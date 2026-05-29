from __future__ import annotations


class NanoAgentError(Exception):
    """nanoagent 所有框架级异常的基类。"""


class FatalError(NanoAgentError):
    """不可恢复的框架错误，直接上抛、不被吞。

    与「工具内业务异常」相对：工具异常会被 AgentLoop._invoke 转成
    ToolResult(is_error=True) 喂回模型 self-heal（DESIGN §5.5、§14.3）；
    FatalError 表示框架本身处于不应继续的状态，_emit / _invoke 都不得吞它。
    """
