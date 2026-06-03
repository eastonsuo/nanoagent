from __future__ import annotations

from nanoagent.tools.decorator import tool

# 第三方/重依赖在函数内部延迟 import，使「import builtin」本身零依赖、可在无网络/未装包时加载。


@tool
def read_file(path: str) -> str:
    """读取文本文件内容。"""
    with open(path, encoding="utf-8") as f:
        return f.read()


@tool
def write_file(path: str, content: str) -> str:
    """把内容写入文本文件，返回确认信息。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {path}（{len(content)} 字符）"


@tool
def list_files(directory: str, pattern: str = "*") -> list:
    """列出目录下匹配 glob 模式的文件路径。"""
    import glob
    import os

    return sorted(glob.glob(os.path.join(directory, pattern)))


@tool
def run_shell(command: str) -> str:
    """执行 shell 命令，返回 stdout+stderr（v0.1 无沙箱，危险性靠 v0.3 权限策略约束）。"""
    import subprocess

    proc = subprocess.run(command, shell=True, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).strip()


@tool
def web_search(query: str, k: int = 5) -> list:
    """用 DuckDuckGo 检索，返回前 k 条「标题 — 链接」。"""
    try:
        from ddgs import DDGS                  # 新包名（duckduckgo-search 已改名为 ddgs）
    except ImportError:
        from duckduckgo_search import DDGS     # 旧包名兜底（会有 deprecation 警告，建议 pip install ddgs）

    with DDGS() as ddgs:
        return [f"{r['title']} — {r['href']}" for r in ddgs.text(query, max_results=k)]


BUILTIN_TOOLS = [read_file, write_file, list_files, run_shell, web_search]
