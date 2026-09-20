# Looma

> **Skills that run, pause, think, and continue.**  
> **让 Skill 不再只是“告诉 Agent 怎么做”，而是让 Agent 真正进入程序执行流。**

Looma 是 **Agent-Embedded Programming（AEP，智能体嵌入式编程）** 的一种 Python 实现。

> **Looma 不启动 Agent，也不负责 Agent / subagent 的并发执行。**  
> Looma 运行在已经存在的 Coding Agent 宿主环境中。程序到达 `agent(...)` 时只产生一份给宿主 Agent 执行的任务说明并暂停；真正的推理、工具调用、subagent 创建、并发调度与结果汇总全部由当前宿主 Agent 原生完成。

这里先区分三个层次：

```text
Agent-Embedded Programming = 编程范式
Executable Skill           = AEP 的一种 Skill 封装形态
Looma                      = AEP 的一个 Python Runtime / Framework 实现
```

**Agent-Embedded Programming** 指的是：

> **把宿主 Agent 作为一种可暂停、可恢复的智能计算单元，直接嵌入普通程序控制流。**

在 AEP 中，程序继续拥有 `if`、`for`、`while`、函数调用和异常处理等控制权；Codex、Claude Code、SDW 等已经运行中的宿主 Coding Agent 提供语义理解、分析、判断、规划、Review、原生 subagent 与并发调度能力；具体 Runtime 实现只负责 suspend、state、replay、resume 与边界协议。

**Executable Skill（可执行 Skill）** 可以作为这种范式的一种 Skill 封装形态：Skill 不再只是 Markdown 中的说明和提示词，而可以与真正的程序控制流、循环、状态、函数调用、暂停与恢复机制结合。

Looma 提供了其中一种具体实现。

使用 Looma，你可以继续用普通 Python 编写 `if`、`for`、`while`、函数和脚本，只在真正需要智能判断的位置插入：

```python
decision = agent(...)
```

程序运行到这里会暂停，把任务交给已经存在的 **Codex / Claude Code / SDW / 其他 Coding Agent 宿主**。

Agent 完成后，Looma 重新运行原来的 Python 命令，并自动恢复到原来的逻辑位置继续执行。

**无需在你的 Workflow 中再次配置 LLM API、API Key、Endpoint、Model SDK 或第二套 Agent Loop。**


---

# 功能特性

Looma 当前围绕 AEP 提供以下能力：

| 能力 | 说明 |
|---|---|
| **普通 Python 控制流** | 继续使用 `if / for / while / function`，不要求改写成 Graph DSL |
| **Host-native Agent Boundary** | `agent(...)` 只产生任务说明并暂停；当前宿主 Agent 原生完成推理与工具调用 |
| **Durable Step** | `step(...)` 持久化已完成结果，replay 时不会重复执行已完成副作用 |
| **Suspend / Replay / Resume** | Agent 工作期间 Python 进程可以退出，之后通过 same-command replay 恢复 |
| **多轮 Agent Workflow** | 一个 Workflow 中可以多次 `agent(...)`，支持循环、分支和多阶段流程 |
| **多脚本 Workflow** | 可以编排已有独立 Python 脚本/工具，不需要把工程重写成单文件 |
| **严格 Resume Contract** | `agent2script` 必须与 `expected_output` 完全一致，否则拒绝执行 |
| **Result Guard** | Agent 业务结果必须先写入 `output.result_file` 且为合法 JSON，才允许恢复 |
| **Host-native Subagent / 并发** | 程序只描述可并行任务；subagent、并发调度和汇总完全由宿主原生实现 |
| **Host-independent Boundary** | Looma 不依赖某个模型 API；Codex、Claude Code、SDW 等宿主可按同一边界语义工作 |
| **Executable Skill** | Wheel 内置 AEP Skill，告诉宿主如何处理 suspend、task、result 和 resume |
| **可测试的持久化执行** | 已有 process restart、loop、多 Agent、多脚本、resume guard 等自动化测试 |

其中并发能力尤其需要注意：

```text
Looma / Python
    ↓
返回“这些任务可以独立执行”的任务说明
    ↓
Host Agent
    ├─ 顺序执行
    └─ 或使用宿主原生 subagents 并发执行
            ↓
          汇总结果
            ↓
       写 result_file
            ↓
       Resume Workflow
```

Looma **不创建线程来模拟 Agent 并发，也不调用任何 Agent CLI / SDK / API 来启动 subagent**。并发是宿主 Agent 的执行策略，而 Looma 只定义任务边界和程序恢复语义。

---

# 核心原则

Looma 的实现遵循下面这些原则。它们也是 AEP 在 Looma 中最重要的设计约束。

### 1. Program owns control flow

**程序拥有控制流。**

循环、分支、终止条件、确定性计算和业务状态都应由普通 Python 表达：

```python
for item in items:
    result = step(process, item)
    review = agent(task="审核结果", input=result)

    if review["done"]:
        break
```

Agent 参与程序，但不取代程序。

### 2. Looma describes work; the host executes work

**Looma 描述任务，宿主执行任务。**

`agent(...)` 的本质不是“调用 Agent”，而是生成一份 `script2agent` 任务说明：

```text
task
input
output_schema
result_file
expected_output
```

当前已经运行的宿主 Agent 自己决定怎样完成它。

### 3. Never launch another Agent

**Looma 永远不负责创建第二个 Agent。**

禁止把 Looma 实现成：

```text
Looma → codex CLI
Looma → Claude Code CLI
Looma → Agent SDK
Looma → LLM API
Looma → subprocess → another Agent
```

模型访问、会话、上下文、工具、终端和 subagent 都属于当前宿主。

### 4. Concurrency belongs to the host

**并发属于宿主执行策略。**

如果任务说明包含多个无依赖子任务，宿主可以：

```text
Host Agent
   ├─ subagent A
   ├─ subagent B
   └─ subagent C
          ↓
        gather
```

也可以顺序完成。

Looma 只表达 **what to do**，宿主决定 **how to execute it**。

### 5. Keep the Agent / Script boundary small

Agent 和 Script 之间只传递必要信息：

```text
script2agent
agent2script
result_file
```

业务结果不塞进 `agent2script`，运行时内部状态也不暴露给 Agent。

### 6. expected_output is a Resume Contract

`expected_output` 不是建议，而是恢复契约。

只有：

```text
actual.script == expected_output.script
actual.args   == expected_output.args
actual.keys   == {"script", "args"}
```

全部成立，Looma 才允许继续执行。

### 7. Side effects must be replay-safe

Replay 会重新从 Workflow 入口执行，因此有副作用或高成本的工作应该放进 `step(...)`。

```python
result = step(run_tests, repo)
```

已经完成的 step 在 replay 时直接返回历史结果，而不会重复执行。

### 8. Resume should return to the original program

Looma 默认通过 **same-command replay/resume** 恢复，而不是要求用户管理：

```text
resume.py
workflow_id
continuation_id
program_counter
```

目标是让：

```python
result = agent(...)
```

在逻辑上仍然表现得像一个普通函数调用。

### 9. Host capability is an optimization, not a semantic dependency

Workflow 的正确性不应该依赖某个宿主是否支持 subagent、特定模型或某种并发机制。

宿主能力可以让任务更快、更强，但同一任务说明在能力较弱的宿主上仍应能够采用串行或简化策略完成。


---

## Why Agent-Embedded Programming?

要理解 Looma，首先要理解它所实现的 AEP 范式试图解决什么问题。

现在的 Agent Skill 和 Agent Workflow，通常落在两个方向。

### 传统 Skill：有“知识”，没有“运行时”

传统 Skill 通常是：

```text
SKILL.md
  ↓
告诉 Agent：
- 应该怎么分析
- 应该调用什么工具
- 应该遵循什么流程
```

它非常适合表达：

- 规则
- SOP
- Prompt
- 工具使用方法
- 领域经验

但 Skill 本身通常没有真正的：

```text
Python control flow
state
loop
checkpoint
suspend
resume
durable execution
```

一旦任务需要：

```text
脚本执行
→ Agent 判断
→ 再执行脚本
→ Agent 再判断
→ 循环直到满足条件
```

往往就开始依赖大量 Prompt 协调和 Glue Code。

---

### 传统 Agent Workflow Framework：有运行时，但通常需要自己再接一套 LLM

另一种常见做法是：

```python
client = OpenAI(...)
agent = SomeAgentFramework(...)
workflow = Graph(...)

while ...:
    result = client.responses.create(...)
```

这种方式能实现复杂 Workflow，但通常意味着应用需要自己管理：

- LLM API Key
- Endpoint
- Model SDK
- Model Selection
- Agent Loop
- Session
- Tool Calling
- Retry
- Context
- Token / API Cost

但如果你本来就在使用 Codex、Claude Code、SDW 等 Coding Agent，这些能力其实已经存在于宿主中。

**为什么还要在 Workflow 里再造第二个 Agent？**

---

## AEP 的核心思路：让宿主 Agent 成为程序的一部分

> **并发属于宿主执行策略，而不是 Looma Runtime 语义。**  
> 如果一个 `script2agent.task` 描述了多个相互独立的子任务，程序返回的是“请宿主完成这些任务”的说明。宿主是否使用 subagent、启动多少个 subagent、是否并发、如何隔离 workspace、如何汇总结果，都由当前宿主自身决定。Looma 不调用任何 Agent CLI / SDK / API 来实现这些能力。


AEP 的抽象结构是：

```text
                 Python Program
                      │
             deterministic code
                      │
                  agent(...)
                      │
                      ▼
             script2agent boundary
                      │
                      ▼
      Codex / Claude Code / SDW / ...
             existing host agent
                      │
                      ▼
             agent2script boundary
                      │
                      ▼
              same Python command
                      │
                      ▼
               replay / resume
                      │
                      ▼
              continue Python
```

也就是说：

> **程序拥有流程控制权，宿主 Coding Agent 提供智能，Runtime 负责把两者连接起来。**

Looma 是这一结构的一种 Python 实现。

---

# Agent-Embedded Programming

**Agent-Embedded Programming（AEP）** 把 Agent 从“程序外部的模型服务”变成“程序内部可恢复的智能计算单元”。

在这个范式下，Skill 也可以从“说明文档”扩展为“可执行能力”。

可以用下面三类形态来理解它们的差异：

| 范式 | Skill / Workflow 是什么 | LLM 在哪里 | 程序控制流 |
|---|---|---|---|
| Traditional Skill | Prompt / Markdown / SOP | 宿主 Agent | 主要由 Agent 自己理解 |
| LLM Workflow Framework | Graph / Agent Framework / Orchestrator | 应用自己的 LLM API | Framework 控制 |
| **Agent-Embedded Programming / Executable Skill** | **Skill + Program Runtime + Agent Boundary** | **宿主 Coding Agent** | **普通程序控制流** |

AEP 的目标不是替代 Codex、Claude Code 或 SDW。

恰恰相反：

> **AEP 把这些已有 Coding Agent 视为可以被程序复用的 Intelligence Runtime。**

在这种范式下，Skill 只需要描述：

- 什么时候需要 Agent
- Agent 应该解决什么问题
- Agent 输入是什么
- Agent 输出结构是什么
- Script 和 Agent 如何交接

而不再需要重新实现模型访问层。

---

# What does Looma enable?

Looma 希望解决的是这种代码：

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
            task="分析当前实验结果，判断是否已经满足目标；如果没有，给出下一轮参数。",
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

从开发者视角，这就是普通 Python：

```text
for
 ↓
function
 ↓
agent
 ↓
if
 ↓
next loop
```

没有：

```text
OpenAI client
Anthropic client
API key
LLM endpoint
Agent SDK
Graph DSL
manual resume
workflow callback
```

但底层实际上已经完成了一次可恢复 Agent Workflow。

---

# The effect

## 1. Agent 可以真正进入普通 Python 函数

以前：

```python
result = some_llm_api(...)
```

现在：

```python
result = agent(
    task="判断测试是否通过，并给出下一步",
    input=test_result,
    output_schema=Review,
)
```

这个 `agent()` 不是一个普通 LLM API 包装器。

它代表：

```text
当前 Python 程序
    ↓
保存状态
    ↓
退出
    ↓
宿主 Agent 完成任务
    ↓
重新执行原命令
    ↓
Replay
    ↓
agent() 像普通函数一样返回
    ↓
程序继续
```

---

## 2. Agent 可以自然出现在循环里

```python
@workflow
def repair(repo):

    for attempt in range(5):

        test_result = step(run_tests, repo)

        decision = agent(
            task="分析测试失败原因，判断是否需要继续修改。",
            input=test_result,
            output_schema=dict,
        )

        if decision["done"]:
            return test_result

        step(apply_fix, repo, decision["fix"])
```

这正是 Looma 要解决的核心问题：

> **当 Python 函数还没有逻辑结束时，调用宿主 Agent；Agent 完成后，原函数能够继续。**

---

## 3. Script 和 Agent 各做自己擅长的事情

```text
Agent
────────────────
理解
分析
判断
规划
Review
语义推理


Script
────────────────
计算
解析
IO
测试
写文件
数据库
固定规则
确定性执行
```

Looma 把两者通过明确协议连接起来：

```text
script2agent
agent2script
```

---

## 4. 不需要重复建设 LLM 接入层

Looma **不会**要求你的业务代码配置：

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
BASE_URL
MODEL_NAME
LLM SDK
```

模型访问、会话、上下文、工具权限、Shell、文件系统等能力由宿主 Coding Agent 提供。

Looma 只处理：

```text
Python control flow
suspend
state
replay
resume
Agent/Script boundary
```

这使同一个 Workflow 有机会运行在不同 Coding Agent 宿主之上。

---

# How it works

Looma V0.1 使用 **same-command replay/resume**。

假设你原本运行：

```bash
python main.py --input data.json
```

代码：

```python
@workflow
def process(data):
    x = step(preprocess, data)

    decision = agent(
        task="判断采用 A 还是 B",
        input=x,
        output_schema=Decision,
    )

    if decision.choice == "A":
        return step(run_a, x)

    return step(run_b, x)
```

第一次执行：

```text
python main.py
      │
      ▼
preprocess()
      │
      ▼
agent(...)
      │
      ▼
persist workflow state
      │
      ▼
emit script2agent
      │
      ▼
exit 75
```

宿主 Agent 完成任务后：

```text
Codex / Claude Code / SDW
      │
      ├── reads script2agent
      │
      ├── executes task
      │
      ├── writes agent-result.json
      │
      └── returns agent2script
```

而这个 `agent2script` 默认就是：

```json
{
  "script": "/usr/bin/python3",
  "args": [
    "/project/main.py",
    "--input",
    "data.json"
  ]
}
```

也就是：

> **重新执行原来的命令。**

第二次执行时：

```text
python main.py
      │
      ▼
Replay
      │
      ├── step(preprocess) → 直接返回历史结果
      │
      └── agent(...)       → 直接返回 Agent 结果
                              │
                              ▼
                         continue Python
```

因此 Resume 不需要暴露：

```text
resume.py
workflow_id
continuation_id
program counter
```

这些全部由 Looma Runtime 管理。

---

# The boundary protocol

Looma 保留一个非常小的 Agent / Script 边界。

## script2agent

Script 把结构化任务交给宿主 Agent：

```json
{
  "script": {
    "path": "/project/main.py",
    "function": "process",
    "class": null
  },
  "output": {
    "agent_input": {
      "metrics": {}
    },
    "result_file": "/project/.looma/runs/.../agent-result.json",
    "output_schema": {
      "type": "object"
    }
  },
  "task": "分析当前结果并决定下一步。",
  "prompt": "...fixed protocol prompt...",
  "expected_output": {
    "script": "/usr/bin/python3",
    "args": ["/project/main.py"]
  }
}
```

## agent2script

Agent 完成后只返回：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py"]
}
```

业务结果不塞进 `agent2script`。

业务结果写入：

```text
output.result_file
```

这使 Agent / Script 边界保持简单、稳定、可机器校验。

## Guarded agent2script validation

`expected_output` 不只是提示信息，而是 **恢复命令契约**。

Looma 会对 Agent 返回的 `agent2script` 做严格校验：

```text
actual.script == expected_output.script
actual.args   == expected_output.args
actual.keys   == {"script", "args"}
```

只有完全一致时，命令才允许执行。

推荐由宿主 / 执行器把 Agent 的最终 JSON 保存为文件，并通过：

```bash
looma handoff \
  --request .looma/runs/<run-id>/events/<event>-script2agent.json \
  --response agent2script.json
```

完成校验和恢复。

如果 Agent 返回了不同脚本、不同参数、额外字段，或者 Agent result 尚未写入，Looma：

```text
1. 不执行 Agent 返回的命令
2. 返回 exit code 76
3. 输出 <<<AGENT2SCRIPT_ERROR>>> 结构化错误
4. 错误中同时给出 expected_output 与 actual_output
5. 宿主应把该错误反馈给同一个 Agent，让 Agent 修正后重试
```

例如 Agent 错误返回：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/other.py"]
}
```

而期待的是：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py"]
}
```

则 `other.py` **不会被执行**。

对于通过校验的命令，Looma 还会从 workflow state 中恢复原始 `cwd` 后再执行，从而尽可能回到原 workflow 的原始运行上下文。

> 注意：真正的强制校验点是 Looma handoff / Host Adapter。若某个宿主绕过 handoff，直接自行执行 Agent 返回的任意命令，Runtime 无法在命令执行之前拦截它。因此 AEP Skill 要求宿主把所有 agent2script 执行统一经过该校验点。

---

# Core API

Looma 的第一版只暴露三个核心概念。

## `@workflow`

定义一个可恢复 Workflow。

```python
@workflow
def main():
    ...
```

---

## `step()`

把一个确定性操作变成 durable step：

```python
parsed = step(parse_document, path)
test_result = step(run_tests, repo)
```

第一次执行真正运行函数。

Replay 时：

```text
step()
 ↓
history hit
 ↓
return cached result
```

因此副作用不会因为 replay 被重复执行。

适合：

- 文件写入
- 数据库写入
- subprocess
- 测试
- 网络请求
- 大规模解析
- 昂贵计算
- 任何不能安全重复执行的操作

---

## `agent()`

定义一个交还给当前宿主 Coding Agent 的任务边界：

```python
review = agent(
    task="Review 当前结果并决定下一步。",
    input=result,
    output_schema=Review,
)
```

首次执行：

```text
agent()
 ↓
生成给当前宿主的任务说明
 ↓
script2agent
 ↓
suspend / return control to host
```

恢复后：

```text
agent()
 ↓
history/result hit
 ↓
return Review(...)
```

因此业务代码可以把 Agent 当成“能够跨进程暂停的函数调用”。

---

# Examples

项目内置了一组常见的 Agent-Embedded Programming 编程场景，不只是最小 API Demo，而是可以直接映射到真实工程的控制流模式：

| Example | 场景 | 核心控制流 |
|---|---|---|
| `examples/basic.py` | 单次 Agent 判断 | `step → agent → step` |
| `examples/branching.py` | Agent 决定分支 | `agent → if / elif / else` |
| `examples/loop.py` | 有界迭代优化 | `for → step → agent → break/continue` |
| `examples/while_retry.py` | 校验失败后重试 | `while → validate → agent → retry` |
| `examples/code_repair.py` | 自动测试/修复闭环 | `pytest → agent repair → pytest` |
| `examples/batch_review.py` | 批量数据审核 | `for each → step → agent → collect` |
| `examples/generate_validate.py` | Agent 生成 + 程序校验 | `agent edits artifact → deterministic validation → loop` |
| `examples/multi_script_workflow/` | 多脚本 Workflow | `collect.py → transform.py → agent → report.py` |
| `examples/multi_stage_agent_workflow/` | 多阶段 Agent/Script Workflow | `prepare.py → Agent → analyze.py → Agent → gate.py → summary/detailed` |

例如代码修复场景保持普通 Python 的流程控制：

```python
@workflow
def repair_until_green(repo, max_attempts=3):
    for attempt in range(max_attempts):
        tests = step(run_tests, repo)

        if tests["returncode"] == 0:
            return tests

        agent(
            task="分析失败原因并直接修改仓库，使测试通过。",
            input={"attempt": attempt, "tests": tests},
            output_schema=RepairResult,
        )

    return step(run_tests, repo)
```

这里的循环、终止条件和测试执行仍由 Python 控制；Agent 只负责需要语义推理和代码修改的部分。

完整说明见 `examples/README.md`。

---

# Installation

## Install the published wheel

V0.1.1 wheel 已直接发布到仓库，可无需 clone 安装：

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.1/looma_runtime-0.1.1-py3-none-any.whl
```

安装后：

```bash
looma status
looma skill-path
```

## Development install

```bash
git clone https://github.com/datanger/Looma.git
cd Looma

pip install -e .
```

## Build wheel

```bash
python -m pip install build
python -m build --wheel
```

生成：

```text
dist/looma_runtime-0.1.1-py3-none-any.whl
```

安装：

```bash
pip install dist/looma_runtime-0.1.1-py3-none-any.whl
```

GitHub Actions 会自动：

```text
Python 3.10
Python 3.11
Python 3.12
Python 3.13
      ↓
pytest
      ↓
build wheel
      ↓
looma-wheel artifact
```

---

# The Looma Skill

Looma 本身同时提供：

```text
src/looma/skills/
└── agent-embedded-programming/
    └── SKILL.md
```

这不是一个普通“提示词 Skill”。

它同时描述：

```text
Skill semantics
+
Python programming model
+
Agent/Script contract
+
Runtime behavior
+
Replay rules
+
Host Agent execution rules
```

因此 Looma Skill 更接近：

> **Agent-Embedded Programming Skill / Executable Skill Specification**

宿主 Coding Agent 不仅知道“应该怎么做”，还知道：

- 什么是 `@workflow`
- 什么是 `step()`
- 什么是 `agent()`
- 遇到 exit code `75` 应该做什么
- 如何处理 `script2agent`
- Agent 结果应该写到哪里
- 为什么最后只返回 `agent2script`
- 为什么恢复命令应该与原命令相同
- 如何让 Python 循环继续

查看安装后的 Skill：

```bash
looma skill-path
```

---

# Traditional Skill vs Executable Skill

这里比较的是 **Skill 形态**，不是 Looma 与传统 Skill。

传统 Skill：

```text
Markdown / Prompt / SOP
  ↓
Agent understands instructions
  ↓
Agent orchestrates actions
```

AEP 下的 Executable Skill：

```text
Skill specification
  +
Program Runtime
  +
Agent / Script Boundary
  ↓
Executable / resumable program flow
```

区别在于：传统 Skill 主要向 Agent 提供知识、规则和操作方法；Executable Skill 进一步把这些能力连接到真实程序控制流，使 Skill 可以参与循环、状态迁移、确定性脚本执行以及 Agent 调用。

> **Executable Skill 是 AEP 可以采用的一种 Skill 形态；Looma 只是它的一种具体实现。**

---

# Agent-Embedded Programming vs API-centric LLM Workflows

这里比较的是 **编程范式**，不是 Looma 与其它框架。

一种常见的 API-centric LLM Workflow 结构是：

```text
Application
   ↓
Workflow / Agent Framework
   ↓
LLM Client
   ↓
Model API
```

Agent-Embedded Programming 的结构是：

```text
Program
   ↓
AEP Runtime
   ↓
Agent Boundary
   ↓
Existing Coding Agent Host
   ↓
Agent result
   ↓
Program continues
```

两种方式都可以构建复杂智能 Workflow，但关注点不同。

API-centric Workflow 通常把模型调用本身作为应用的一部分，因此应用负责模型客户端、Endpoint、鉴权、Agent Loop 等能力。

AEP 则优先复用已经存在的 Coding Agent 宿主，把重点放在：

- 如何让 Agent 进入普通程序控制流；
- 如何在 Agent 执行期间暂停程序；
- 如何持久化状态；
- 如何恢复原程序；
- 如何让 Agent 与确定性脚本在循环中协作。

AEP 本身并不限定具体 Runtime、编程语言或边界协议。**Looma 是 AEP 的一个 Python 实现，并选择了 `script2agent / agent2script` 与 same-command replay/resume 作为当前实现机制。**

---

# Local state

默认状态目录：

```text
.looma/
├── invocations/
└── runs/
    └── <run-id>/
        ├── state.json
        └── events/
            ├── 0000-step-result.json
            ├── 0001-script2agent.json
            └── 0001-agent-result.json
```

查看：

```bash
looma status
```

清理：

```bash
looma reset --yes
```

---

# Replay model

Looma V0.1 不保存真实 Python 调用栈，也不动态拼接 Python 源代码。

恢复方式是：

> **重新运行原程序 + replay 已完成 event。**

因此要求：

- `step()` / `agent()` 调用顺序稳定；
- suspend 和 resume 之间不要修改会改变 replay 路径的代码；
- 跨边界值必须可 JSON 序列化；
- file handle、socket、thread、process、CUDA context 等运行时对象不能跨边界保存；
- 副作用应进入 `step()`。

如果当前执行路径和历史不一致：

```text
ReplayMismatchError
```

Looma 会直接拒绝继续，而不是静默进入错误状态。

---

# Current status

Looma 目前处于 **V0.1 / experimental**。

当前 Runtime 自动化测试已经验证：

```text
ordinary Python
     ↓
agent()
     ↓
suspend
     ↓
host contract result
     ↓
validated same-command agent2script
     ↓
replay
     ↓
agent() returns
     ↓
continue original function
```

这里的自动化测试使用程序模拟 Host Contract；真实 Coding Agent 的执行发生在已经存在的宿主会话中，不由 Looma 在测试进程里启动。

以及：

```text
for / while
    ↓
multiple agent calls
    ↓
multiple process exits
    ↓
same-command resumes
    ↓
workflow completion
```

---

# Roadmap

接下来重点包括：

- Host-native integration contract：让 Codex / SDW / Claude Code 等宿主更自然地消费 `script2agent`，但不由 Looma 启动 Agent
- 更严格的 Agent result schema 校验
- Workflow history / inspect
- Retry / failure policies
- Concurrent workflow instances
- Pluggable state store
- Durable distributed backend
- 更丰富的 Step primitive
- 更完整的 Skill packaging / discovery
- Host-native subagent / concurrency task conventions
- 更好的 observability

---

# Philosophy

**Agent-Embedded Programming** 的核心并不是：

> “再做一个 Agent。”

而是：

> **让已经存在的 Agent 成为程序的一部分。**

Looma 只是这一思想的一种实现。

不是：

```text
Application calls LLM API
```

而是：

```text
Program
  ↕
Skill Runtime
  ↕
Host Agent
```

最终我们希望写 Agent Workflow 时，代码看起来仍然像代码：

```python
result = step(run_test, repo)

review = agent(
    task="判断结果是否满足目标",
    input=result,
)

if review["done"]:
    return result
```

> **Looma — Skills that run, pause, think, and continue.**
