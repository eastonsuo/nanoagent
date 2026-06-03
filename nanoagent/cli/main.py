"""命令行入口：`nanoagent` 命令（pyproject [project.scripts] → cli.main:main）。

v0.1 基础版用标准库 input() 做 REPL（prompt-toolkit 的补全 / 历史留作后续打磨）；
底层是一个 ChatSession，整段对话复用同一个 Context（记得上文）。
配置：模型读 NANOAGENT_MODEL（默认 gpt-4o-mini）；API key 读 OPENAI_API_KEY；
切 DeepSeek 等端点用 OPENAI_BASE_URL（如 https://api.deepseek.com）。
"""
from __future__ import annotations

import os

from nanoagent import __version__


def main() -> None:
    from nanoagent.api import Agent
    from nanoagent.tools.builtin import BUILTIN_TOOLS

    model = os.environ.get("NANOAGENT_MODEL", "gpt-4o-mini")
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  未设置 OPENAI_API_KEY（DeepSeek 等兼容端点另设 OPENAI_BASE_URL）。")

    session = Agent(model, tools=BUILTIN_TOOLS).session()
    print(f"nanoagent {__version__} — 输入问题开始对话（Ctrl-D / Ctrl-C 退出）")

    while True:
        try:
            prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not prompt:
            continue
        result = session.send(prompt)
        print(result.output)
        total = result.usage.get("total_tokens")
        if total:
            print(f"  （{result.turns} 轮 · {total} tokens）")


if __name__ == "__main__":
    main()
