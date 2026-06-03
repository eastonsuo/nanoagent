"""命令行入口：`nanoagent` 命令（pyproject [project.scripts] → cli.main:main）。

v0.1 基础版用标准库 input() 做 REPL（prompt-toolkit 的补全 / 历史留作后续打磨）；
底层是一个 ChatSession，整段对话复用同一个 Context（记得上文）。
配置：模型读 NANOAGENT_MODEL（默认 gpt-4o-mini）；API key 读 OPENAI_API_KEY；
切 DeepSeek 等端点用 OPENAI_BASE_URL（如 https://api.deepseek.com）。
"""
from __future__ import annotations

import os

from nanoagent import __version__


_PROVIDER_KEYS = ("OPENAI_API_KEY", "DEEPSEEK_API_KEY", "MOONSHOT_API_KEY")


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


def main() -> None:
    from prompt_toolkit import PromptSession
    from nanoagent.api import Agent
    from nanoagent.tools.builtin import BUILTIN_TOOLS

    model = _default_model()
    if not any(os.environ.get(k) for k in _PROVIDER_KEYS):
        print("⚠️  未检测到 API key（设 OPENAI_API_KEY / DEEPSEEK_API_KEY 之一即可）。")

    chat = Agent(model, tools=BUILTIN_TOOLS).session()
    print(f"nanoagent {__version__} · 模型 {model} — 输入问题开始对话（Ctrl-D / Ctrl-C 退出）")

    # 用 prompt_toolkit 而非 input()：方向键 / 行编辑 / 历史，且正确解码 UTF-8 输入
    # （input() 在非 UTF-8 locale 下、或按方向键时会把转义序列/坏字节读进字符串，导致请求编码崩溃）。
    repl = PromptSession()
    while True:
        try:
            prompt = repl.prompt("> ").strip()
            if not prompt:
                continue
            result = chat.send(prompt)
        except (EOFError, KeyboardInterrupt):     # Ctrl-D / Ctrl-C（等输入或调模型时都算）→ 干净退出
            print()
            break
        except Exception as e:                    # 单轮业务出错只提示、不退出整个 REPL
            print(f"⚠️  出错：{type(e).__name__}: {e}")
            continue
        print(result.output)
        total = result.usage.get("total_tokens")
        if total:
            print(f"  （{result.turns} 轮 · {total} tokens）")


if __name__ == "__main__":
    main()
