from __future__ import annotations

import inspect
import types
import typing
from typing import Any

# Python 标量类型 → JSON Schema type（v0.1 支持范围，见 v0.1-design.md §4.2 映射表）
_JSON_PRIMITIVES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def _unwrap_optional(tp: Any) -> tuple[Any, bool]:
    """Optional[X] / Union[X, None] / X | None -> (inner, is_optional)。

    仅在「恰好一个非 None 分支」时解出 inner；其余 Union 原样返回（v0.1 不深挖多分支 Union）。
    """
    origin = typing.get_origin(tp)
    union_type = getattr(types, "UnionType", None)   # PEP 604（3.10+）的 X | Y
    if origin is typing.Union or (union_type is not None and origin is union_type):
        args = typing.get_args(tp)
        non_none = [a for a in args if a is not type(None)]
        is_optional = len(non_none) < len(args)
        if len(non_none) == 1:
            return non_none[0], is_optional
        return tp, is_optional
    return tp, False


def _json_for(tp: Any) -> dict:
    """把一个（已解包 Optional 的）Python 类型映射成 JSON Schema 片段。"""
    if tp in _JSON_PRIMITIVES:
        return {"type": _JSON_PRIMITIVES[tp]}
    origin = typing.get_origin(tp) or tp
    if origin in (list, set, frozenset, tuple):
        return {"type": "array"}        # v0.1 不展开 items（见 §4.2 优化空间）
    if origin is dict:
        return {"type": "object"}
    return {"type": "string"}           # 兜底：未识别 / 无注解按 string


def build_schema(fn: Any, name: str, description: str) -> dict:
    """从函数签名 + 类型注解生成 OpenAI Function Calling schema。

    无默认值且非 Optional 的参数进 required；类型注解无法解析时整体退化为无类型（全 string）。
    """
    sig = inspect.signature(fn)
    try:
        hints = typing.get_type_hints(fn)
    except Exception:
        hints = {}
    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in sig.parameters.items():
        if pname == "self":
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        tp = hints.get(pname)
        if tp is None:
            prop, is_optional = {"type": "string"}, False
        else:
            inner, is_optional = _unwrap_optional(tp)
            prop = _json_for(inner)
        properties[pname] = prop
        has_default = param.default is not inspect.Parameter.empty
        if not has_default and not is_optional:
            required.append(pname)
    parameters: dict = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": parameters},
    }
