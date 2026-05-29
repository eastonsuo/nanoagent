"""Tool 系统：@tool 装饰器、注册表、签名→OpenAI schema 生成、内置工具。

依赖方向：tools 依赖 core（实现 Tool 协议），core 不反向依赖 tools。
内置工具在 ``nanoagent.tools.builtin``（按需 import，避免无谓拉起第三方依赖）。
"""

from nanoagent.tools.decorator import FunctionTool, tool
from nanoagent.tools.registry import ToolRegistry
from nanoagent.tools.schema import build_schema

__all__ = ["tool", "FunctionTool", "ToolRegistry", "build_schema"]
