"""api.py —— 唯一「知道全部模块」的装配层（不在 core 内，可 import 全部）。

把字符串模型名解析成 LLMClient（core 永远只见解析后的客户端），并提供两个平级入口：
  - Agent       ：一次性任务，每次 run 新建 Context（跨 run 无记忆、相互隔离）；
  - ChatSession ：多轮对话，复用同一个 Context（带记忆）。
二者共享同一个无状态 AgentLoop——状态归 Context、编排归 Loop（DESIGN §5.6 / §14.3-Q3）。
"""
from __future__ import annotations

import os

from nanoagent.core import AgentLoop, AgentResult, Context, Message

# 内置默认 system prompt（放装配层、不进 core）；Agent(system_prompt=...) 可整体覆盖，传 "" 则不加。
DEFAULT_SYSTEM_PROMPT = (
    "你是一个能调用工具完成任务的助手。需要外部信息或操作时，调用合适的工具，"
    "不要编造工具的返回结果；信息齐了就用自然语言直接回答。"
    "当你不再需要调用工具、直接给出答复时，本轮任务即视为结束。"
)


# 按模型名前缀自动选 OpenAI 兼容端点：(前缀, base_url, 专属 api_key 环境变量)。
# 命中则自动配 base_url、并优先读该供应商的 key（没有则回落到 OpenAI SDK 默认的 OPENAI_API_KEY）。
_PROVIDERS = [
    ("deepseek", "https://api.deepseek.com", "DEEPSEEK_API_KEY"),
    ("moonshot", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
    ("kimi", "https://api.moonshot.cn/v1", "MOONSHOT_API_KEY"),
]


def _detect_endpoint(model: str):
    """按模型名前缀推断 (base_url, api_key 环境变量名)；未命中返回 (None, None)＝OpenAI 默认。"""
    for prefix, base_url, key_env in _PROVIDERS:
        if model.startswith(prefix):
            return base_url, key_env
    return None, None


def resolve_model(model):
    """字符串模型名 → LLMClient；已是 LLMClient 则原样返回。

    自动选端点：模型名以已知前缀开头（如 ``deepseek-chat``）时，自动配好对应 base_url，
    只需设供应商 key（DeepSeek 用 DEEPSEEK_API_KEY，没有则回落 OPENAI_API_KEY）即可。
    显式 ``OPENAI_BASE_URL`` 环境变量优先级最高，可覆盖自动判断、接任意自建/未知端点。
    """
    if not isinstance(model, str):
        return model
    from nanoagent.llm import OpenAICompatClient   # 懒加载：仅用真实客户端时才需 openai

    base_url = os.environ.get("OPENAI_BASE_URL")          # 显式覆盖优先
    api_key = None
    if base_url is None:
        base_url, key_env = _detect_endpoint(model)        # 按模型名自动选端点
        if key_env:
            api_key = os.environ.get(key_env)              # 供应商专属 key；None 时 SDK 回落 OPENAI_API_KEY
    return OpenAICompatClient(model, base_url=base_url, api_key=api_key)


class Agent:
    """一次性任务的入口：每次 run 新建 Context（跨 run 无记忆、相互隔离）。

    「无状态」指跨 run；单次 run 内仍是多轮 ReAct。本类只持有配置（loop + system_prompt）。
    """

    def __init__(self, model, tools=None, *, system_prompt: str | None = None,
                 hooks=None, stop=None, max_turns: int = 20):
        self._loop = AgentLoop(resolve_model(model), tools or [], hooks, stop, max_turns)
        # None → 用内置默认 prompt；显式 "" 则不加 system 消息
        self._system = DEFAULT_SYSTEM_PROMPT if system_prompt is None else system_prompt

    def run(self, prompt: str) -> AgentResult:
        ctx = Context()
        if self._system:
            ctx.add(Message(role="system", content=self._system, pinned=True))
        ctx.add(Message(role="user", content=prompt))
        return self._loop.run(ctx)

    def session(self) -> "ChatSession":          # 便捷工厂：复用同一个 loop 开个有状态会话（非「包含」ChatSession）
        return ChatSession(self._loop, self._system)


class ChatSession:
    """多轮对话入口：与 Agent 平级，复用同一个无状态 AgentLoop + 持续累积的同一个 Context。"""

    def __init__(self, loop: AgentLoop, system_prompt: str | None = None):
        self._loop = loop
        self.ctx = Context()
        if system_prompt:
            self.ctx.add(Message(role="system", content=system_prompt, pinned=True))

    def send(self, prompt: str) -> AgentResult:
        self.ctx.add(Message(role="user", content=prompt))
        return self._loop.run(self.ctx)          # 原地增长同一个 ctx
