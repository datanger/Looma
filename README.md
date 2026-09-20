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

> **程序拥有控制流；宿主 Agent 提供智能；Runtime 负责暂停、恢复与持久化。**

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

Looma 当前支持普通 Python 分支与循环、多次 Agent 调用、多脚本 Workflow、持久化 replay、结构化 Agent result 校验、严格 resume 校验、Workflow inspect 和独立 run 隔离。

## Install

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.2/looma_runtime-0.1.2-py3-none-any.whl
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

仓库只保留一个完整案例：[examples/stock_analysis_agent/](examples/stock_analysis_agent/)。

它实现一个短期股票分析 Agent：

```text
AKShare 获取 K线 / 成交量 / 换手率
        ↓
代码计算市场特征
        ↓
宿主 Agent 上网检索最近几日新闻
        ↓
代码检查证据完整性
        ↓
宿主可用 native subagents 并行分析
        ↓
证据不足则定向补充研究并循环
        ↓
生成最终分析报告
```

这个案例同时展示 multi-script、loop、多次 Agent boundary、structured result、durable replay 和 Host-native subagent concurrency。

## Documentation

更完整的技术说明已从 README 移到：

- [AGENT.md](AGENT.md) — Runtime、Host Contract、Replay、Result/Resume Contract、状态与开发约束
- [docs/agent-embedded-programming.md](docs/agent-embedded-programming.md) — AEP 编程范式
- [docs/design.md](docs/design.md) — Looma Runtime 设计

## Status

当前版本：**v0.1.2 / experimental**

CI 覆盖 Python 3.10、3.11、3.12、3.13，并验证 process restart、loop、多 Agent、多脚本、result schema guard、resume guard、run isolation 与 wheel 安装。

> **Looma — Skills that run, pause, think, and continue.**
