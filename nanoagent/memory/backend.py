"""InMemoryBackend —— 进程内 dict 实现，v0.1 working memory 的契约占位。

retrieve 在 v0.1 不做向量 / 语义检索（那是 semantic memory，v0.2+ 基于向量），
只朴素返回最近写入的 k 个值——契约对、实现简陋，符合「形状定对、实现可最简」。
"""
from __future__ import annotations

from typing import Any


class InMemoryBackend:
    """实现 MemoryBackend 协议（store / retrieve / delete），结构化、无需继承。"""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def store(self, key: str, value: Any, metadata: dict | None = None) -> None:
        self._store[key] = value

    def retrieve(self, query: str, k: int = 5) -> list[Any]:
        # v0.1 无语义检索：返回最近写入的 k 个值
        return list(self._store.values())[-k:]

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
