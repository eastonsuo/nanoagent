# nanoagent 示例

## `full_tour.py` — 完整功能巡览

一个脚本串起 v0.1 的全部能力，分两部分：

- **Part A · 离线机制演示**：用 `EchoClient`（脚本预设 LLM 响应）驱动，**无需 API key、不联网**。工具是真实执行的，只有 LLM 的「决策」是预设的——用来看清 loop / hook / 权限的机制。**总会跑。**
- **Part B · 真实自主 agent**：检测到任一供应商 key 时才跑。真实模型自主决定调哪些工具，并演示多轮对话记忆与累计用量。

### 运行

离线（无需 key）：

```bash
python examples/full_tour.py
```

接真实模型（再多跑 Part B）——设任一 key，模型名前缀自动选端点：

```bash
export DEEPSEEK_API_KEY=sk-...     # 或 OPENAI_API_KEY / MOONSHOT_API_KEY
python examples/full_tour.py
```

### 覆盖的 v0.1 功能

| 功能 | 在示例中的体现 | 代码位置 |
|---|---|---|
| `@tool` 自定义工具 | `word_count`（签名 + docstring → schema 自动生成） | 文件顶部 |
| 内置工具 | `list_files` / `read_file` / `write_file` … | `BUILTIN_TOOLS` |
| 自定义 Hook（可观测） | `TraceHook`：run 边界 / 每轮 token / 工具结果 | 覆盖 8 点中的 4 个 |
| 自定义 Hook（权限） | `ReadOnlyGuard`：拒绝写/执行（软拒绝 → 自愈） | `before_tool` |
| 停止策略 | `MaxTurnsStop(6)` 安全上限 | `Agent(stop=...)` |
| `Agent.run` 一次性 | Part A / B1 | — |
| `ChatSession` 多轮记忆 | B2：第二问能记起名字 | `agent.session()` |
| **token 用量** | **单轮**（`after_model`）/ **累计**（`result.usage`、`ctx.usage`） | 全程 |
| 离线 / 真实端点 | `EchoClient` vs 字符串模型名自动识别 | Part A vs B |

### 预期输出（离线部分节选）

```
  ▶ run 开始
  · LLM 本轮 42 tokens → 请求工具: word_count
  ✓ word_count 执行完毕 → 1234
  · LLM 本轮 50 tokens → 请求工具: list_files
  ✓ list_files 执行完毕 → ["/.../context.py", ...]
  · LLM 本轮 33 tokens → 请求工具: write_file
  ⛔ 权限拒绝：write_file（只读模式）
  · LLM 本轮 20 tokens → 直接作答（无工具）
  ■ 停止：done

停止原因：done · 轮数：4 · 累计 145 tokens
```
