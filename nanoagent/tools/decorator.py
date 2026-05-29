from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Callable

from nanoagent.tools.schema import build_schema

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_NAME = 64


def _validate_name(name: str) -> None:
    """工具名规则：^[a-z][a-z0-9_]*$ 且 ≤64 字符（DESIGN §14.3）。"""
    if not _NAME_RE.match(name):
        raise ValueError(f"工具名非法（须匹配 ^[a-z][a-z0-9_]*$）: {name!r}")
    if len(name) > _MAX_NAME:
        raise ValueError(f"工具名超过 {_MAX_NAME} 字符: {name!r}")


def _first_doc_line(fn: Callable) -> str:
    doc = inspect.getdoc(fn)
    if not doc:
        return ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


@dataclass
class FunctionTool:
    """`@tool` 的产物：满足 core.Tool 协议（name / description / schema + __call__）。"""

    fn: Callable[..., Any]
    name: str
    description: str
    schema: dict

    def __call__(self, **kwargs: Any) -> Any:
        return self.fn(**kwargs)


def tool(
    fn: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Any:
    """把普通函数注册为工具。`@tool` 或 `@tool(name=..., description=...)` 均可。

    名字默认取函数名（强制 ^[a-z][a-z0-9_]*$ 且 ≤64）；描述默认取 docstring 首行；
    schema 由函数签名 + 类型注解自动生成（见 tools/schema.py）。重名校验在注册表（registry）做。
    """

    def wrap(f: Callable) -> FunctionTool:
        t_name = name or f.__name__
        _validate_name(t_name)
        desc = description or _first_doc_line(f)
        return FunctionTool(fn=f, name=t_name, description=desc,
                            schema=build_schema(f, t_name, desc))

    return wrap(fn) if fn is not None else wrap
