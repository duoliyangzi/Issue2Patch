# Issue2Patch

**Issue → 规划 → 工具改代码 → 自动验证 → 导出补丁与轨迹**

面向研发效能的 **AI Coding Agent**：根据自然语言缺陷描述，在指定代码工作区内多轮调用工具完成修复，并产出可回放轨迹与 `git` 补丁。

仓库：https://github.com/duoliyangzi/Issue2Patch

---

## 项目能力

| 能力 | 说明 |
|------|------|
| **AI Coding 闭环** | 输入 Issue + 工作区 + 验证命令，自动定位、修改、跑测直至通过或达步数上限 |
| **ReAct 多轮** | 推理 → 调用工具 → 观察结果 → 再决策，直到 `submit_fix` |
| **任务规划** | `update_todos` 维护 pending / in_progress / completed 清单 |
| **工作区工具** | 列目录、读文件、写文件、执行 shell（如 `pytest`） |
| **轨迹与补丁** | 输出 `trajectory.json` / `trajectory.html` 与 `fix.patch` |
| **本地控制台** | FastAPI Web UI：一键 Demo、填 Issue、运行 Agent、查看结果 |
| **自建评测** | 8 类典型缺陷用例，可跑 resolve rate 报告 |

**典型流程**

```text
Issue / 需求描述
    ↓
LangGraph ReAct Agent（多轮 Tool Calling）
    ↓
list / read / write / run_command …
    ↓
验证命令通过 → submit_fix
    ↓
fix.patch + 轨迹回放
```

---

## 技术栈

### Agent 与编排（主路径）

| 技术 | 用途 |
|------|------|
| **LangChain** | `@tool` 工具定义、消息与模型封装 |
| **LangGraph** | `create_react_agent` 实现 ReAct 多轮循环（Agent Harness） |
| **langchain-openai** | 对接 OpenAI 兼容接口（通义 / 阿里云 MaaS 等） |

### 工程与交互

| 技术 | 用途 |
|------|------|
| **Python 3.10+** | 主语言 |
| **FastAPI + Uvicorn** | 本地 Web 控制台与任务 API |
| **Typer + Rich** | CLI（`issue2patch`） |
| **Pydantic / PyYAML** | 配置与数据结构 |
| **pytest** | Demo 与评测验证命令 |

### 可选 / 对照路径

| 技术 | 用途 |
|------|------|
| **mini-swe-agent（MIT）** | 可选引擎 `mini`：bash-only 长程循环，见 `NOTICE.md` |
| **LiteLLM** | mini 路径下的多模型路由 |

默认引擎：`ISSUE2PATCH_ENGINE=langchain`。

---

## 工具一览（LangChain）

| 工具 | 作用 |
|------|------|
| `list_files` | 列出工作区内文件 |
| `read_file` | 读取源码 / 测试 |
| `write_file` | 写入或覆盖文件 |
| `run_command` | 在工作区执行命令（复现 / 跑测） |
| `update_todos` | 更新结构化任务计划 |
| `submit_fix` | 声明修复完成并提交摘要 |

---

## 快速开始

```bash
cd Issue2Patch
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -e .

cp .env.example .env   # Windows 可用 copy
# 编辑 .env：OPENAI_API_KEY、OPENAI_API_BASE、ISSUE2PATCH_MODEL
```

**CLI**

```bash
issue2patch init-demo -t examples/buggy_calc_run

issue2patch run \
  -w examples/buggy_calc_run \
  -f examples/buggy_calc_run/issue.md \
  -v "python -m pytest -q" \
  -e langchain \
  -o runs/demo
```

**Web UI**

```bash
issue2patch ui
# 打开 http://127.0.0.1:8765
```

成功后查看 `runs/demo/fix.patch`、`runs/demo/trajectory.html`。

---

## 环境变量

| 变量 | 含义 |
|------|------|
| `OPENAI_API_KEY` | API Key |
| `OPENAI_API_BASE` | OpenAI 兼容 Base URL |
| `ISSUE2PATCH_MODEL` | 如 `openai/qwen3.8-flash` |
| `ISSUE2PATCH_ENGINE` | `langchain`（默认）或 `mini` |

---

## 评测

自建 8 例小缺陷集（非 SWE-bench）：

```bash
python -m eval.run_eval --step-limit 20
```

报告：`eval/output/LATEST_REPORT.md`（示例结果：验证通过率 8/8）。

---

## 目录结构（核心）

```text
src/issue2patch/
  langchain_agent.py   # LangChain 工具 + LangGraph ReAct（主路径）
  runner.py            # 统一入口（langchain / mini）
  cli.py               # CLI
  web/                 # FastAPI 控制台
  planning.py          # todos 解析
  patch_export.py      # git diff → fix.patch
  trajectory.py        # 轨迹 JSON / HTML
examples/buggy_calc/   # Demo：故意写错的计算器
eval/                  # 自建评测集与跑分脚本
```

---

## 许可

- 本仓库产品层（Issue 工作流、LangChain 路径、Web、评测等）见项目说明。  
- 可选 mini 路径包含 [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) 代码，遵循 MIT，详见 `LICENSE.md`、`NOTICE.md`。
