# Issue2Patch

**Issue → 自主规划 → 沙箱改代码 → 跑测 → 导出 patch + 轨迹回放**

面向求职/作品集的 Coding Agent 应用（研发效能场景），不是通用聊天客服。  
执行底座基于 [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)（MIT），产品层 `issue2patch` 为自研：结构化 todos 规划、Issue 工作流 CLI、patch 导出、轨迹 HTML 回放、通义/LiteLLM 配置。

与「校园咸鱼」分工：咸鱼 = 业务 Multi-Agent；本仓库 = Agent Harness（长程执行 + 沙箱 + 评测轨迹）。

---

## 能力一览

| 能力 | 说明 |
|------|------|
| ReAct 多轮 | 模型推理 → bash 工具 → observation → 再决策 |
| 自主规划 | 强制/解析 ` ```todos``` ` 清单（pending / in_progress / completed） |
| 沙箱 | `local`（工作目录内 subprocess）或 `docker`（挂载工作区） |
| 产出 | `fix.patch` + `trajectory.json` + `trajectory.html` |
| 模型 | LiteLLM；默认示例走 DashScope `dashscope/qwen-plus` |

---

## 评测

自建 8 例小缺陷集（非 SWE-bench）：

```bash
python -m eval.run_eval --step-limit 20
```

报告见 `eval/output/LATEST_REPORT.md`。

```bash
issue2patch ui
# 浏览器打开 http://127.0.0.1:8765
```

页面上可：一键准备 Demo → 编辑 Issue → 运行 Agent → 打开轨迹回放 / 查看 patch。

```bash
cd Issue2Patch
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
pip install -e .

copy .env.example .env   # 填入 DASHSCOPE_API_KEY 或 OPENAI_API_KEY
```

准备 demo 仓库并运行：

```bash
issue2patch init-demo -t examples/buggy_calc_run
issue2patch run ^
  -w examples/buggy_calc_run ^
  -f examples/buggy_calc_run/issue.md ^
  -v "python -m pytest -q" ^
  -s local ^
  -o runs/demo
```

成功后查看：

- `runs/demo/fix.patch`
- `runs/demo/trajectory.html`

Docker 沙箱（需本机 Docker；Windows 建议路径兼容的挂载）：

```bash
issue2patch run -w ... -f ... -s docker --docker-image python:3.12-slim -o runs/demo-docker
```

---

## 环境变量

| 变量 | 含义 |
|------|------|
| `DASHSCOPE_API_KEY` | 通义（LiteLLM `dashscope/...`） |
| `OPENAI_API_KEY` / `OPENAI_API_BASE` | OpenAI 兼容网关 |
| `ISSUE2PATCH_MODEL` | 默认模型，如 `dashscope/qwen-plus` |
| `MSWEA_MODEL_NAME` | 兼容 mini-swe-agent 的模型变量 |

---

## 仓库结构（产品相关）

```text
src/issue2patch/          # 自研产品层
  agent.py                # PlanningAgent（todos 写入轨迹）
  cli.py                  # issue2patch CLI
  planning.py             # 解析 ```todos```
  patch_export.py         # git diff → fix.patch
  trajectory.py           # JSON + HTML 回放
  config/issue2patch.yaml # Issue 工作流提示词
src/minisweagent/         # 上游 harness（保留，便于对照）
examples/buggy_calc/      # 故意写错的计算器 + issue.md
```

---

## 简历可写要点（示例）

- 基于 bash tool-use 的 ReAct 多轮 Coding Agent，覆盖 Issue→Patch 闭环  
- 引入结构化任务规划（todos）并写入可回放轨迹  
- 支持 local / Docker 沙箱执行与 `git diff` 补丁导出  
- （可选后续）SWE-bench Verified 子集评测与 resolve rate  

---

## 致谢与许可

- 执行循环 / 环境 / LiteLLM 对接大量来自 **mini-swe-agent**，见 `NOTICE.md` 与 `LICENSE.md`（MIT）。  
- Issue2Patch 产品层（规划、CLI、轨迹回放、示例工作流）为本仓库新增。
