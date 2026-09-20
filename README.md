# Looma

> **Skills that run, pause, think, and continue.**  
> **让 Skill 不再只是“告诉 Agent 怎么做”，而是让 Agent 真正进入程序执行流。**

Looma 是 **Agent-Embedded Programming（AEP，智能体嵌入式编程）** 的一种 Python 实现。

这里先区分三个层次：

```text
Agent-Embedded Programming = 编程范式
Executable Skill           = AEP 的一种 Skill 封装形态
Looma                      = AEP 的一个 Python Runtime / Framework 实现
```

**Agent-Embedded Programming** 指的是：

> **把宿主 Agent 作为一种可暂停、可恢复的智能计算单元，直接嵌入普通程序控制流。**

在 AEP 中，程序继续拥有 `if`、`for`、`while`、函数调用和异常处理等控制权；Codex、Claude Code、SDW 等宿主 Coding Agent 提供语义理解、分析、判断、规划和 Review 等智能能力；具体 Runtime 实现负责两者之间的 suspend、state、replay、resume 与边界协议。

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

调用宿主 Coding Agent：

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
script2agent
 ↓
suspend
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

# Installation

## Install the published wheel

V0.1 wheel 已直接发布到仓库，可无需 clone 安装：

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.0/looma_runtime-0.1.0-py3-none-any.whl
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
dist/looma_runtime-0.1.0-py3-none-any.whl
```

安装：

```bash
pip install dist/looma_runtime-0.1.0-py3-none-any.whl
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

当前已经验证：

```text
ordinary Python
     ↓
agent()
     ↓
suspend
     ↓
host coding agent
     ↓
same-command agent2script
     ↓
replay
     ↓
agent() returns
     ↓
continue original function
```

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

- Host Adapter：Codex / SDW / Claude Code 更自动地消费 `script2agent`
- Agent result schema 更严格的校验
- Workflow history / inspect
- Retry / failure policies
- Concurrent workflow instances
- Pluggable state store
- Durable distributed backend
- 更丰富的 Step primitive
- 更完整的 Skill packaging / discovery
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
