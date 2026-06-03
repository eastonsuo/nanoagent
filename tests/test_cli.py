"""cli/ 单测 —— 默认模型按供应商 key 自动选（REPL 交互部分不在此测）。"""
from nanoagent.cli.main import _default_model


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
