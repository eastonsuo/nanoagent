"""nanoagent v0.1 · 完整功能巡览（full tour）

一个脚本串起 v0.1 的全部能力：
  • @tool 自定义工具（签名 + docstring → OpenAI schema 自动生成）
  • 内置工具（read_file / list_files / write_file / run_shell / web_search）
  • 自定义 Hook：可观测性（8 生命周期点中的 on_start / after_model / after_tool / on_stop）
  • 自定义 Hook：权限策略（只读护栏，拒绝写/执行 → 软拒绝、模型自愈）
  • 停止策略 MaxTurnsStop（安全上限）
  • Agent.run 一次性任务
  • ChatSession 多轮对话 + 记忆
  • token 用量统计（单轮 / 跨轮累计）
  • 两种 LLM 客户端：EchoClient 离线脚本（无需 key）/ 真实端点按模型名自动识别

运行
----
离线（无需 key，跑 Part A 机制演示；工具真实执行，只有 LLM 决策是脚本预设）：

    python examples/full_tour.py

接真实模型（再多跑 Part B 自主 agent + 多轮记忆）：设任一供应商 key 即可，
模型名前缀会自动选端点（DeepSeek / Kimi / OpenAI 兼容）：

    export DEEPSEEK_API_KEY=sk-...        # 或 OPENAI_API_KEY / MOONSHOT_API_KEY
    python examples/full_tour.py
"""
from __future__ import annotations

import os

from nanoagent import Agent, tool
from nanoagent.core import BaseHook, LLMResponse, Message, ToolCall, ToolDecision
from nanoagent.llm import EchoClient
from nanoagent.strategies import MaxTurnsStop
from nanoagent.tools.builtin import BUILTIN_TOOLS

# 用绝对路径，脚本在任何 CWD 下都能找到仓库里的真实文件
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
README = os.path.join(REPO, "README.md")
CORE_DIR = os.path.join(REPO, "nanoagent", "core")


# ── 1. 自定义工具：@tool 自动把「签名 + docstring」变成 OpenAI function schema ──
@tool
def word_count(path: str) -> int:
    """统计文本文件的单词数（按空白切分）。"""
    with open(path, encoding="utf-8") as f:
        return len(f.read().split())


# ── 2. 自定义 Hook：可观测性 ── 纯观察，覆盖 8 点里的 4 个，其余沿用 BaseHook 空实现
class TraceHook(BaseHook):
    """把 harness 内部活动打到控制台：run 边界、每轮 token、工具执行结果。"""

    def on_start(self, ctx) -> None:
        print("  ▶ run 开始")

    def after_model(self, ctx, response: LLMResponse) -> None:
        tokens = response.usage.get("total_tokens", 0)
        calls = response.message.tool_calls
        if calls:
            names = ", ".join(c.name for c in calls)
            print(f"  · LLM 本轮 {tokens} tokens → 请求工具: {names}")
        else:
            print(f"  · LLM 本轮 {tokens} tokens → 直接作答（无工具）")

    def after_tool(self, ctx, call: ToolCall, result) -> None:
        preview = result.content.replace("\n", " ")[:60]
        print(f"  ✓ {call.name} 执行完毕 → {preview}")

    def on_stop(self, ctx, reason) -> None:
        print(f"  ■ 停止：{reason.value}")


# ── 3. 自定义 Hook：权限策略 ── before_tool 是 8 点里唯一有返回值的，可拒绝调用
class ReadOnlyGuard(BaseHook):
    """只读护栏：拒绝一切写/执行类工具。

    返回 allowed=False 是「软拒绝」——loop 只对该次调用回填一条 denial、让模型换路，
    不终止整轮（见 DESIGN §5.3）。所以下面 Part A 里被拒后，模型仍能继续作答。
    """

    BLOCKED = {"write_file", "run_shell"}

    def before_tool(self, ctx, call: ToolCall) -> ToolDecision:
        if call.name in self.BLOCKED:
            print(f"  ⛔ 权限拒绝：{call.name}（只读模式）")
            return ToolDecision(allowed=False, reason=f"只读模式禁止 {call.name}")
        return ToolDecision(allowed=True)


def banner(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


# ── Part A：离线机制演示（EchoClient 脚本驱动；无需 key，总会跑）──
def demo_offline() -> None:
    banner("Part A · 离线机制演示（EchoClient，无需 API key）")
    print("LLM 的决策由脚本预设，但工具是真实执行的——用来看清 loop / hook / 权限的机制。")

    # 预设 4 轮 LLM 响应：调自定义工具 → 调内置工具 → 试图写文件(将被拒) → 作答
    script = [
        LLMResponse(
            Message(role="assistant", tool_calls=[
                ToolCall("c1", "word_count", {"path": README})]),
            usage={"total_tokens": 42}),
        LLMResponse(
            Message(role="assistant", tool_calls=[
                ToolCall("c2", "list_files", {"directory": CORE_DIR, "pattern": "*.py"})]),
            usage={"total_tokens": 50}),
        LLMResponse(
            Message(role="assistant", tool_calls=[
                ToolCall("c3", "write_file", {"path": os.path.join(REPO, "_demo.txt"),
                                              "content": "x"})]),
            usage={"total_tokens": 33}),
        LLMResponse(
            Message(role="assistant",
                    content="README 已统计、core 目录已列出；写文件被只读护栏拦下，故只汇报读取结果。"),
            usage={"total_tokens": 20}),
    ]

    agent = Agent(
        EchoClient(script),                       # 传客户端实例（而非模型名）= 离线
        tools=[word_count, *BUILTIN_TOOLS],       # 自定义工具 + 5 个内置工具
        hooks=[TraceHook(), ReadOnlyGuard()],     # 可观测 + 权限：两个 harness 策略
        stop=MaxTurnsStop(6),                     # 停止策略：安全上限（happy path 用不到）
    )
    result = agent.run("统计 README 词数、列出 core 的 .py，并尝试写一个文件。")

    print(f"\n最终答复：{result.output}")
    print(f"停止原因：{result.stop_reason.value} · 轮数：{result.turns} · "
          f"累计 {result.usage.get('total_tokens', 0)} tokens")


# ── Part B：真实自主 agent（需 key；展示自主调工具 + 多轮记忆 + 用量）──
def pick_model() -> str | None:
    """按已设的供应商 key 选模型；都没有则返回 None（跳过 Part B）。"""
    explicit = os.environ.get("NANOAGENT_MODEL")
    if os.environ.get("DEEPSEEK_API_KEY"):
        return explicit or "deepseek-chat"
    if os.environ.get("MOONSHOT_API_KEY"):
        return explicit or "moonshot-v1-8k"
    if os.environ.get("OPENAI_API_KEY"):
        return explicit or "gpt-4o-mini"
    return None


def demo_live(model: str) -> None:
    banner(f"Part B · 真实自主 agent（模型 {model}）")
    agent = Agent(
        model,                                    # 字符串模型名 → 自动选端点（resolve_model）
        tools=[word_count, *BUILTIN_TOOLS],
        hooks=[TraceHook(), ReadOnlyGuard()],
    )

    # B1 · 一次性任务：模型自主决定调哪些工具
    print("\n[B1] Agent.run —— 一次性任务，模型自主调工具：")
    task = (f"用 list_files 列出目录 {CORE_DIR} 下的 .py 文件，"
            f"再用 word_count 统计 {README} 的单词数，最后一句话汇总。")
    r1 = agent.run(task)
    print(f"\n答复：{r1.output}")
    print(f"轮数 {r1.turns} · {r1.usage.get('total_tokens', 0)} tokens")

    # B2 · 多轮对话：同一个 ChatSession 复用同一个 Context = 记忆
    print("\n[B2] ChatSession —— 多轮对话，跨轮记忆：")
    chat = agent.session()
    chat.send("我叫小明，请记住我的名字。")
    r2 = chat.send("我叫什么名字？")
    print(f"\n第二问答复：{r2.output}")
    print(f"整场会话累计 {chat.ctx.usage.get('total_tokens', 0)} tokens")


def main() -> None:
    demo_offline()

    model = pick_model()
    if model is None:
        banner("Part B 已跳过（未检测到 API key）")
        print("设任一供应商 key 后重跑，即可看到真实自主 agent + 多轮记忆：")
        print("    export DEEPSEEK_API_KEY=sk-...   # 或 OPENAI_API_KEY / MOONSHOT_API_KEY")
        return
    try:
        demo_live(model)
    except Exception as e:                          # 网络 / key / 余额问题 → 友好提示，不抛栈
        print(f"\n⚠️  真实调用失败：{type(e).__name__}: {e}")
        print("   检查 API key / 网络 / 余额后重试。")


if __name__ == "__main__":
    main()
