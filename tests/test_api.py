"""api/ 单测 —— Agent / ChatSession 装配层（用 EchoClient 当 model，不联网）。

resolve_model 对「非字符串」原样返回，故传 EchoClient 即可全链路单测，不触发 openai。
"""
from nanoagent.api import Agent, ChatSession, _detect_endpoint, resolve_model
from nanoagent.llm import EchoClient


def test_detect_endpoint_deepseek():
    base, key_env = _detect_endpoint("deepseek-chat")
    assert base == "https://api.deepseek.com"
    assert key_env == "DEEPSEEK_API_KEY"


def test_detect_endpoint_openai_default_unknown():
    assert _detect_endpoint("gpt-4o-mini") == (None, None)


def test_detect_endpoint_kimi():
    base, _key = _detect_endpoint("moonshot-v1-8k")
    assert base == "https://api.moonshot.cn/v1"


def test_resolve_model_passthrough():
    c = EchoClient()
    assert resolve_model(c) is c                 # 非字符串原样返回（不触发 openai import）


def test_agent_run_is_stateless_across_runs():
    a = Agent(EchoClient(), tools=[])
    r1 = a.run("hi")
    r2 = a.run("yo")
    assert r1.output == "echo: hi"
    assert r2.output == "echo: yo"
    assert r1.context is not r2.context          # 每次 run 新建 Context、互不相关


def test_agent_default_system_prompt_pinned():
    r = Agent(EchoClient(), tools=[]).run("hi")
    sys = [m for m in r.context.messages if m.role == "system"]
    assert sys and sys[0].pinned                 # 默认 system prompt 被 pin


def test_agent_empty_system_prompt_skips_system():
    r = Agent(EchoClient(), tools=[], system_prompt="").run("hi")
    assert not any(m.role == "system" for m in r.context.messages)


def test_chatsession_remembers_context():
    s = Agent(EchoClient(), tools=[]).session()
    s.send("我叫小明")
    n1 = len(s.ctx.messages)
    s.send("你好")
    assert len(s.ctx.messages) > n1              # 同一个 ctx 持续累积（有记忆）
    assert s.ctx.messages[0].role == "system"    # 会话起始带 pinned system prompt


def test_session_is_factory_sharing_loop():
    a = Agent(EchoClient(), tools=[])
    s = a.session()
    assert isinstance(s, ChatSession)
    assert s._loop is a._loop                    # 共享同一个无状态 AgentLoop（非包含）
