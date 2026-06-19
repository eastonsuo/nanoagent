"""命令行入口：`nanoagent` 命令（pyproject [project.scripts] → cli.main:main）。

REPL 用 prompt-toolkit（方向键 / 行编辑 / 历史，且正确解码 UTF-8 输入）；
底层是一个 ChatSession，整段对话复用同一个 Context（记得上文）。
退出：输入 `/exit`（或 `/quit` / `/q`），Ctrl-D / Ctrl-C 也可——都会打印告别语 + 本次会话累计用量。
配置：模型读 NANOAGENT_MODEL（默认 gpt-4o-mini）；API key 读 OPENAI_API_KEY；
切 DeepSeek 等端点用 OPENAI_BASE_URL（如 https://api.deepseek.com）。
"""
from __future__ import annotations

import os

from nanoagent import __version__


_PROVIDER_KEYS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY")

# 退出关键词（slash 命令，大小写不敏感）。"这种" 关键词退出，而非只能 Ctrl-D。
_EXIT_COMMANDS = {"/exit", "/quit", "/q"}
_FAREWELL = "好的，再见！👋 随时欢迎再来找我帮忙~"


def _default_model() -> str:
    """没显式设 NANOAGENT_MODEL 时，按已设的供应商 key 猜默认模型
    （设了 DEEPSEEK_API_KEY 就用 deepseek-chat，端点会被自动识别，无需再设模型名）。"""
    explicit = os.environ.get("NANOAGENT_MODEL")
    if explicit:
        return explicit
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek-chat"
    if os.environ.get("MOONSHOT_API_KEY"):
        return "moonshot-v1-8k"
    return "gpt-4o-mini"


def _is_exit(text: str) -> bool:
    """输入是否为退出命令（/exit /quit /q，忽略大小写与首尾空白）。"""
    return text.strip().lower() in _EXIT_COMMANDS


def _farewell(rounds: int, total_tokens: int) -> str:
    """告别语 + 本次会话累计（rounds=对话回合数，total_tokens=ctx 跨轮累计 token）。"""
    return f"{_FAREWELL}\n  （{rounds} 轮 · {total_tokens} tokens）"


def main() -> None:
    from prompt_toolkit import PromptSession
    from nanoagent.api import Agent
    from nanoagent.tools.builtin import BUILTIN_TOOLS

    model = _default_model()
    if not any(os.environ.get(k) for k in _PROVIDER_KEYS):
        print("⚠️  未检测到 API key（设 OPENAI_API_KEY / DEEPSEEK_API_KEY 之一即可）。")

    chat = Agent(model, tools=BUILTIN_TOOLS).session()
    print(f"nanoagent {__version__} · 模型 {model} — 输入问题开始对话（输入 /exit 退出）")

    repl = PromptSession()
    rounds = 0                                    # 对话回合数：用户成功发问的次数
    while True:
        try:
            prompt = repl.prompt("> ").strip()
        except (EOFError, KeyboardInterrupt):     # Ctrl-D / Ctrl-C 在等输入时 → 退出
            print()
            break
        if not prompt:
            continue
        if _is_exit(prompt):                      # /exit /quit /q → 退出
            break
        try:
            result = chat.send(prompt)
        except KeyboardInterrupt:                 # 模型调用中途 Ctrl-C → 退出
            print()
            break
        except Exception as e:                    # 单轮业务出错只提示、不退出整个 REPL
            print(f"⚠️  出错：{type(e).__name__}: {e}")
            continue
        rounds += 1
        print(result.output)
        total = result.usage.get("total_tokens")
        if total:
            print(f"  （{result.turns} 轮 · {total} tokens）")

    # 统一出口：告别语 + 整场会话累计（ctx.usage 跨 send 累计；轮数=对话回合）
    print(_farewell(rounds, chat.ctx.usage.get("total_tokens", 0)))


if __name__ == "__main__":
    main()
