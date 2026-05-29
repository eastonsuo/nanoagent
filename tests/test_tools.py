"""tools/ 单测 —— 不依赖网络（web_search 只验 schema 不真调）。

对应 v0.1-design.md §4：@tool 包装 / 签名→schema / 类型映射 / 命名校验 / 注册重名 / 内置工具。
注意：本文件不加 `from __future__ import annotations`，使局部函数的注解是真实类型对象，
便于 build_schema 里的 get_type_hints 解析（含局部作用域里的 Optional）。
"""
from typing import Optional

import pytest

from nanoagent.tools import FunctionTool, ToolRegistry, tool
from nanoagent.tools.builtin import (
    BUILTIN_TOOLS,
    list_files,
    read_file,
    run_shell,
    write_file,
)


def test_tool_basic_wrapping():
    @tool
    def greet(name: str) -> str:
        """打招呼。"""
        return f"hi {name}"

    assert isinstance(greet, FunctionTool)
    assert greet.name == "greet"
    assert greet.description == "打招呼。"
    assert greet(name="x") == "hi x"                      # __call__ 转调原函数
    assert greet.schema["type"] == "function"
    assert greet.schema["function"]["name"] == "greet"


def test_schema_required_vs_optional_by_default():
    @tool
    def f(a: str, b: int = 3) -> str:
        """doc。"""
        return ""

    params = f.schema["function"]["parameters"]
    assert params["properties"]["a"] == {"type": "string"}
    assert params["properties"]["b"] == {"type": "integer"}
    assert params["required"] == ["a"]                    # b 有默认值 → 非 required


def test_type_mapping_covers_v01_range():
    @tool
    def f(s: str, i: int, fl: float, b: bool, lst: list, d: dict,
          opt: Optional[int] = None) -> str:
        """doc。"""
        return ""

    props = f.schema["function"]["parameters"]["properties"]
    assert props["s"]["type"] == "string"
    assert props["i"]["type"] == "integer"
    assert props["fl"]["type"] == "number"
    assert props["b"]["type"] == "boolean"
    assert props["lst"]["type"] == "array"
    assert props["d"]["type"] == "object"
    assert props["opt"]["type"] == "integer"              # Optional[int] 解包成 integer
    assert "opt" not in f.schema["function"]["parameters"].get("required", [])


def test_no_param_tool_has_empty_properties():
    @tool
    def ping() -> str:
        """无参工具。"""
        return "pong"

    params = ping.schema["function"]["parameters"]
    assert params == {"type": "object", "properties": {}}  # 无参 → 无 required 键


def test_description_defaults_to_first_docstring_line():
    @tool
    def f(x: str) -> str:
        """第一行说明。

        第二段细节，不应进描述。
        """
        return x

    assert f.description == "第一行说明。"


def test_custom_name_and_description():
    @tool(name="my_tool", description="自定义描述")
    def f(x: str) -> str:
        return x

    assert f.name == "my_tool"
    assert f.description == "自定义描述"


@pytest.mark.parametrize("bad", ["Upper", "1num", "has-dash", "has space", "", "a" * 65])
def test_invalid_name_raises(bad):
    with pytest.raises(ValueError):
        tool(name=bad)(lambda: None)


def test_registry_register_and_duplicate():
    reg = ToolRegistry()

    @tool
    def a(x: str) -> str:
        """d。"""
        return x

    reg.register(a)
    assert "a" in reg
    assert len(reg) == 1
    assert reg.get("a") is a
    with pytest.raises(ValueError):
        reg.register(a)                                   # 重名报错


def test_registry_register_all():
    reg = ToolRegistry()
    reg.register_all(BUILTIN_TOOLS)
    assert len(reg) == len(BUILTIN_TOOLS)
    assert "read_file" in reg


def test_builtin_read_write_list(tmp_path):
    p = tmp_path / "x.txt"
    assert "已写入" in write_file(path=str(p), content="hello world")
    assert read_file(path=str(p)) == "hello world"
    files = list_files(directory=str(tmp_path), pattern="*.txt")
    assert str(p) in files


def test_builtin_run_shell():
    out = run_shell(command="echo nano")
    assert "nano" in out


def test_builtin_tools_have_valid_schema():
    for t in BUILTIN_TOOLS:
        fn_schema = t.schema["function"]
        assert t.schema["type"] == "function"
        assert fn_schema["name"] == t.name
        assert fn_schema["description"]                   # 内置工具都有描述
        assert fn_schema["parameters"]["type"] == "object"
