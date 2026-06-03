"""llm/ —— LLMClient 协议的两个实现。

- EchoClient：不联网的测试基石，按预设脚本返回 LLMResponse。
- OpenAICompatClient：包官方 openai SDK，做 core Message ↔ OpenAI dict 双向翻译。

依赖方向：llm 依赖 core（实现 LLMClient 协议），core 不反向依赖 llm。
openai 是重依赖，仅在 OpenAICompatClient.__init__ 内懒加载——
故仅 import 本包不会触发 openai，EchoClient 与双向转换函数都可脱离 openai 单测。
"""
from nanoagent.llm.echo import EchoClient
from nanoagent.llm.openai_compat import OpenAICompatClient

__all__ = ["EchoClient", "OpenAICompatClient"]
