"""cli/ 单测 —— 默认模型按供应商 key 自动选 + 退出命令判定 + 告别语
（REPL 交互本身依赖 TTY、不在此测，故把可测逻辑抽成纯函数）。"""
import pytest

from nanoagent.cli.main import _default_model, _farewell, _is_exit


def test_default_model_explicit_wins(monkeypatch):
    monkeypatch.setenv("NANOAGENT_MODEL", "gpt-4o")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    assert _default_model() == "gpt-4o"


def test_default_model_deepseek_key(monkeypatch):
    monkeypatch.delenv("NANOAGENT_MODEL", raising=False)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    assert _default_model() == "deepseek-chat"


def test_default_model_fallback_openai(monkeypatch):
    for k in ("NANOAGENT_MODEL", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert _default_model() == "gpt-4o-mini"


@pytest.mark.parametrize("text", ["/exit", "/quit", "/q", " /EXIT ", "/Quit"])
def test_is_exit_recognizes_commands(text):
    assert _is_exit(text)


@pytest.mark.parametrize("text", ["exit", "你好", "/exits", "/", "退出", "quit me"])
def test_is_exit_ignores_non_commands(text):
    assert not _is_exit(text)


def test_farewell_contains_message_and_stats():
    line = _farewell(3, 5698)
    assert "好的，再见" in line
    assert "（3 轮 · 5698 tokens）" in line


def test_farewell_zero_session():
    # 立刻退出（没对话）：诚实显示 0 轮 0 tokens，不报错
    assert "（0 轮 · 0 tokens）" in _farewell(0, 0)
