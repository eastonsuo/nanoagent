"""nanoagent —— 一个核心循环 ~30 行的 ReAct 单 agent 框架。

常用入口：

    from nanoagent import Agent, tool

    @tool
    def word_count(path: str) -> int:
        '''统计文本文件的单词数。'''
        return len(open(path).read().split())

    agent = Agent("gpt-4o-mini", tools=[word_count])
    print(agent.run("统计 README.md 有多少单词").output)

一次性任务用 Agent.run；多轮对话用 Agent(...).session().send（见 DESIGN §5.6）。
全部核心契约与数据结构在 ``nanoagent.core``。
"""

__version__ = "0.1.0.dev0"

from nanoagent.api import Agent, ChatSession
from nanoagent.tools import tool

__all__ = ["Agent", "ChatSession", "tool", "__version__"]
