"""memory/ 单测 —— store / retrieve / delete 的基本读写、覆盖、删除。"""
from nanoagent.memory import InMemoryBackend


def test_store_and_retrieve_recent():
    m = InMemoryBackend()
    for i in range(7):
        m.store(f"k{i}", i)
    # 朴素 retrieve：返回最近写入的 k 个值
    assert m.retrieve("any", k=3) == [4, 5, 6]
    assert m.retrieve("any") == [2, 3, 4, 5, 6]   # 默认 k=5


def test_overwrite():
    m = InMemoryBackend()
    m.store("k", "v1")
    m.store("k", "v2")
    assert m.retrieve("any", k=5) == ["v2"]


def test_delete():
    m = InMemoryBackend()
    m.store("a", 1)
    m.store("b", 2)
    m.delete("a")
    assert m.retrieve("any", k=5) == [2]
    m.delete("nonexistent")          # 删不存在的 key 不报错
