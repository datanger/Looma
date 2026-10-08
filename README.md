# Looma

> **Skills that run, pause, think, and continue.**  
> **让 Agent 真正进入普通程序执行流。**

Looma 是 **Agent-Embedded Programming（AEP，智能体嵌入式编程）** 的一个 Python Runtime。

```text
Agent-Embedded Programming = 编程范式
Executable Skill           = AEP 的一种 Skill 封装形态
Looma                      = AEP 的一个 Python 实现
```

AEP 的核心很简单：

> **程序拥有控制流与验收条件；宿主 Agent 提供语义推理与证据获取；Runtime 负责暂停、恢复与持久化。**

Looma 不启动新的 Agent，也不要求 Workflow 再配置一套 LLM API。  
它直接复用当前已经存在的 Codex、Claude Code、SDW 或其他 Coding Agent 宿主。

## Quick example

```python
from dataclasses import dataclass
from looma import workflow, step, agent

@dataclass
class Decision:
    done: bool
    next_config: dict

@workflow
def optimize(config):
    for iteration in range(10):
        metrics = step(run_experiment, config)

        decision = agent(
            task="分析当前结果。满足目标则 done=true，否则给出下一轮参数。",
            input={
                "iteration": iteration,
                "metrics": metrics,
                "config": config,
            },
            input_schema={"type": "object"},
            output_schema=Decision,
        )

        if decision.done:
            return metrics

        config = decision.next_config
```

从代码视角，它仍然只是普通 Python：

```text
for / while / if / function
        ↓
      agent(...)
        ↓
程序暂停
        ↓
当前宿主 Agent 完成任务
        ↓
原命令恢复并 replay
        ↓
agent() 返回
        ↓
程序继续
```

## Core API

| API | 作用 |
|---|---|
| `@workflow` | 定义可暂停、可恢复的 Workflow |
| `step(fn, ...)` | 持久化确定性或有副作用的步骤，replay 时不重复执行 |
| `agent(...)` | 把当前任务交还给已经存在的宿主 Coding Agent |

Looma 当前 `main` 支持普通 Python 分支与循环、多次 Agent 调用、多脚本 Workflow、持久化 replay、可选 Agent input schema 校验、结构化 Agent result 校验、严格 resume 校验、Workflow inspect 和独立 run 隔离。

## AEP + GEPA-style optimization

Looma 还提供一个可选的 `looma.optimization` 辅助层，用于在 AEP Workflow 中表达 GEPA 风格的反思式优化：

- Python 程序拥有 candidate evaluation、预算、停止条件和 acceptance gate；
- evaluator 可以返回 score、trajectory 与 ASI（Actionable Side Information）；
- `request_reflection()` 通过现有 `agent()` 边界把证据交给当前 Host Agent；
- `CandidateProposal` 经过结构校验后，由 Python 更新确定性的 Pareto frontier；
- candidate、frontier 和验收结果都可以通过 `step()` 参与 replay/resume。

这不是第二个 Agent，也不要求安装外部 `gepa` 包。Looma 不引入 direct model client；模型、工具和反思能力仍属于当前 Host Coding Agent。

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.4/looma_runtime-0.1.4-py3-none-any.whl
```

验证安装：

```bash
looma --help
looma skill-path
```

## Runtime commands

```bash
looma status
looma inspect
looma inspect <run-id>
looma skill-path
```

同一个启动命令需要多个独立 Workflow 实例时：

```bash
LOOMA_RUN_KEY=job-a python main.py
LOOMA_RUN_KEY=job-b python main.py
```

## Host boundary

Looma 的边界协议保持很小：

```text
Program
   ↓
script2agent
   ↓
Existing Coding Agent Host
   ↓
result_file + agent2script
   ↓
validate
   ↓
same-command replay / resume
```

Agent/subagent 的推理、工具调用、并发调度与结果汇总都属于宿主本身，不属于 Looma Runtime。

## Example

仓库包含一个 AEP + GEPA-style 优化案例和一个完整的外部数据案例：

- [examples/gepa_optimization/](examples/gepa_optimization/) — 本地确定性 evaluator、Host Agent 反思、acceptance gate、Pareto frontier 和 same-command replay/resume；
- [examples/stock_analysis_agent/](examples/stock_analysis_agent/) — 真实数据与证据门控的综合案例。

它实现一个短期股票分析 Agent：

```text
try AKShare 获取真实行情
        │
        ├─ success → 继续
        │
        └─ failure → 当前宿主联网补充有来源的真实行情
                         ↓
                  程序校验并保存
                         ↓
                 代码计算市场特征
                         ↓
             宿主 Agent 检索近期新闻
                         ↓
               程序执行 Evidence Gate
                         ↓
            宿主完成多维分析 / 可用 native subagents
                         ↓
               程序执行 Analysis Gate
                         ↓
          complete / insufficient_evidence
```

这个案例同时展示 multi-script、loop、多次 Agent boundary、structured result、durable replay、真实数据 fallback、程序化 evidence/analysis gate，以及 Host-native subagent concurrency。Live fallback 明确禁止伪造行情；fixture 只用于确定性 CI。

## Documentation

更完整的技术说明已从 README 移到：

- [AGENTS.md](AGENTS.md) — Codex 标准仓库指令；Runtime、Host Contract、Replay、Result/Resume Contract、状态与开发约束
- [docs/agent-embedded-programming.md](docs/agent-embedded-programming.md) — AEP 编程范式
- [docs/design.md](docs/design.md) — Looma Runtime 设计

## Status

最新发布版本：**v0.1.4 / experimental**。当前开发分支还包含尚未发布的 `input_schema` Agent Input Contract 与可选 AEP + GEPA-style optimization capability。

CI 覆盖 Python 3.10、3.11、3.12、3.13，并验证 process restart、loop、多 Agent、多脚本、result schema guard、resume guard、run isolation 与 wheel 安装。

> **Looma — Skills that run, pause, think, and continue.**
