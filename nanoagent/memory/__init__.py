"""memory/ —— MemoryBackend 协议的实现。

v0.1 只做 working memory，且 working memory 的真身其实是 Context.messages（对话历史）；
InMemoryBackend 是 MemoryBackend 契约的最小实现 + 占位，给 v0.2 文件系统 / episodic memory 留接口形状。
依赖方向：memory 实现 core 的 MemoryBackend 协议（结构化，无需 import core）。
"""
from nanoagent.memory.backend import InMemoryBackend

__all__ = ["InMemoryBackend"]
