from __future__ import annotations

from nanoagent.core import Tool


class ToolRegistry:
    """name -> Tool 的注册表；register 时重名报错（v0.1 不引 namespace 前缀，DESIGN §14.3）。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, t: Tool) -> Tool:
        if t.name in self._tools:
            raise ValueError(f"工具重名: {t.name!r}")
        self._tools[t.name] = t
        return t

    def register_all(self, tools) -> None:
        for t in tools:
            self.register(t)

    def get(self, name: str):
        return self._tools.get(name)

    def all(self) -> list:
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)
