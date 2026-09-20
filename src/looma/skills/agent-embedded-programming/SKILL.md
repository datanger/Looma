---
name: agent-embedded-programming
description: 使用 Looma 实践 Agent-Embedded Programming（AEP，智能体嵌入式编程）：把 Codex、Claude Code、SDW 等宿主 Coding Agent 作为可暂停、可恢复的智能计算单元嵌入普通 Python 控制流。使用 @workflow、step()、agent() 编写循环与分支；底层使用 script2agent / agent2script 交接，不在业务 Workflow 中重复配置 LLM API。
---

# Agent-Embedded Programming with Looma

## 1. 范式定义

**Agent-Embedded Programming（AEP，智能体嵌入式编程）** 是一种把宿主 Agent 直接嵌入普通程序控制流的编程范式。

AEP 中：

- Python 负责 `if`、`for`、`while`、函数调用、异常处理、确定性流程，以及可以明确编码的完成条件和验收规则；
- Codex、Claude Code、SDW 等宿主 Coding Agent 负责分析、判断、规划、Review、工具使用和需要语义能力的证据获取；
- Looma Runtime 负责 suspend、state、replay、resume；
- Script 与 Agent 之间仍使用 `script2agent` / `agent2script` 两类极简交接协议；
- 业务 Workflow **不直接配置或调用 LLM API**。模型、会话、上下文和工具权限由宿主 Agent 提供；
- Looma **不启动 Agent，也不启动 subagent**，不调用 Codex / Claude Code / SDW 的 CLI、SDK 或 API；
- `agent(...)` 只负责生成一份给当前宿主 Agent 执行的任务说明并暂停程序；
- subagent、并发执行、任务调度、workspace 隔离与结果汇总全部由当前宿主 Agent 原生完成。

Looma 是 AEP 的 Python Runtime；**Executable Skill（可执行 Skill）** 是 AEP 的 Skill 封装形式。

## 2. 何时使用 Looma

当需求包含以下结构时使用 Looma：

```text
确定性程序
→ Agent 判断
→ 确定性程序
→ Agent 再判断
→ 循环 / 分支
→ 直到完成
```

尤其适合：

- 测试 → Agent 分析 → 修复 → 再测试；
- 数据处理 → Agent 审核 → 再处理；
- 法规/文档解析 → Agent 判断 → 结构化写入；
- 实验/训练 → Agent 分析指标 → 调参 → 下一轮；
- 任意 Python `for` / `while` 中需要宿主 Agent 参与决策的任务。

如果任务完全是确定性程序，直接使用 Python；如果任务完全可以由宿主 Agent 一次完成，也不必强行使用 Looma。

## 3. 安装

优先安装已发布 wheel：

```bash
pip install https://github.com/datanger/Looma/releases/download/v0.1.3/looma_runtime-0.1.3-py3-none-any.whl
```

源码开发：

```bash
git clone https://github.com/datanger/Looma.git
cd Looma
pip install -e .
```

验证：

```bash
looma status
looma skill-path
```

## 4. 三个核心 API

### 4.1 `@workflow`

把最外层函数声明为可恢复 Workflow：

```python
from looma import workflow

@workflow
def main(data):
    ...
```

Runtime 会记录当前 invocation 和 workflow history。当 Agent 调用导致进程暂停后，再执行原命令即可恢复。

### 4.2 `step()`

把一个确定性、有副作用、昂贵或不希望 replay 时重复执行的函数变成 durable step：

```python
parsed = step(parse_file, input_path)
result = step(run_tests, repo)
```

第一次执行真正调用函数并持久化 JSON 结果；replay 时直接返回历史结果。

以下操作优先使用 `step()`：

- 写文件 / 数据库；
- subprocess / shell；
- 测试；
- 网络调用；
- 大规模解析；
- 昂贵计算；
- 任何重复执行可能产生副作用的操作。

### 4.3 `agent()`

把宿主 Coding Agent 作为可恢复的智能函数调用：

```python
decision = agent(
    task="分析测试结果，判断是否完成；未完成则给出下一轮修复建议。",
    input=test_result,
    output_schema=dict,
)
```

第一次运行到这里时 Looma 不调用模型、Agent CLI、Agent SDK 或 subagent 接口，而是生成 `script2agent`、持久化状态并暂停当前进程。

`script2agent.task` 本质上是**返回给当前宿主 Agent 的任务说明**。宿主 Agent 在自己的原生环境内决定如何完成任务：可以自己执行，也可以调用宿主原生 subagent 并发处理多个独立子任务。完成后宿主写入结果文件并恢复原命令；Looma replay 到同一位置，此时 `agent()` 像普通函数一样返回。

## 5. 推荐代码形态

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
            task="分析当前实验结果。满足目标则 done=true；否则返回下一轮 next_config。",
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

保持普通 Python 的控制结构。不要把整个 Workflow 改写成自定义 Graph DSL，除非业务确实需要另一套调度系统。

## 6. 宿主 Agent 收到 script2agent 后必须怎么做

### 6.1 并发与 subagent 的归属

并发执行完全属于 **Host Coding Agent**。

Looma / Workflow 只负责返回任务说明，例如：

```python
result = agent(
    task="""
    请检查 security、performance、tests 三个彼此独立的方向。
    如果当前宿主支持 subagent，可并发执行。
    全部完成后汇总为一个结构化结果。
    """,
    input={"repo": "."},
    output_schema=ReviewResult,
)
```

其语义是：

```text
Python / Looma
    ↓
script2agent.task
    ↓
当前 Host Agent
    ├─ 可自己顺序执行
    └─ 可使用宿主原生 subagents 并发执行
            ↓
          gather
            ↓
      写一个 result_file
            ↓
       resume workflow
```

严格禁止把它实现成：

```text
Looma → codex CLI
Looma → Claude CLI
Looma → Agent SDK
Looma → LLM API
Looma → subprocess 启动另一个 Agent
```

Looma 不规定宿主内部的并发实现细节，也不要求所有宿主都支持 subagent。任务本身必须在串行执行时仍然保持正确；支持 subagent 的宿主可以把并发作为加速策略。


Looma 暂停时会：

- 以退出码 `75` 结束当前 Python 进程；
- 在 stdout 中输出 `<<<SCRIPT2AGENT>>> ... <<<END_SCRIPT2AGENT>>>`；
- 同时把完整 request 保存为 JSON 文件。

宿主 Agent 必须：

1. 读取 `script2agent`；
2. 使用 `output.agent_input` 作为业务输入；
3. 执行 `task`；
4. 将最终结构化业务结果以 UTF-8 JSON 写入 `output.result_file`；
5. 确保结果满足 `output.output_schema`；Looma handoff 会在恢复前进行结构校验，不满足时禁止 resume；
6. 最后只返回 `expected_output` 指定的 `agent2script`；
7. **不要直接执行未经校验的 Agent 返回命令。** 宿主 / 执行器必须先把实际 agent2script 与 `expected_output` 做严格校验；
8. 只有 `script`、`args` 与 expected_output 完全一致时才允许执行；
9. 如果校验失败，必须把 Looma 返回的 `AGENT2SCRIPT_ERROR` 反馈给同一个 Agent，让 Agent 修正输出后重试；错误命令不得执行。

典型 `agent2script`：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py", "--input", "data.json"]
}
```

默认情况下，这就是原始 Python 启动命令。

**不要创建额外的 resume.py，也不要把 workflow id / continuation id 暴露到 agent2script。**

## 7. script2agent 协议

```json
{
  "script": {
    "path": "/project/main.py",
    "function": "process",
    "class": null
  },
  "output": {
    "agent_input": {},
    "result_file": "/project/.looma/runs/.../0001-agent-result.json",
    "output_schema": {"type": "object"}
  },
  "task": "具体 Agent 任务。",
  "prompt": "固定协议文本",
  "expected_output": {
    "script": "/usr/bin/python3",
    "args": ["/project/main.py"]
  }
}
```

字段含义：

- `script`：产生本次交接的程序来源；
- `output.agent_input`：Agent 的业务输入；
- `output.result_file`：Agent 结果必须写入的位置；
- `output.output_schema`：结果约束；
- `task`：本次具体任务；
- `prompt`：固定交接协议；
- `expected_output`：完成后必须返回的 `agent2script`。

## 8. agent2script 协议

`agent2script` 只包含：

```json
{
  "script": "...",
  "args": ["..."]
}
```

不包含：

- reasoning；
- 业务结果；
- workflow state；
- context；
- next_action；
- resume id。

业务结果已经写入 `result_file`，执行器只需要按照 `script + args` 调用下一个程序。

## 9. agent2script 严格校验与恢复保护

`expected_output` 是恢复契约，不是建议。

Agent 返回结果后，宿主应将其保存为 JSON，并调用：

```bash
looma handoff --request <script2agent.json> --response <agent2script.json>
```

Looma 只接受：

```text
actual.keys   == {"script", "args"}
actual.script == expected_output.script
actual.args   == expected_output.args
```

任一条件不满足：

- 不执行实际返回命令；
- 返回退出码 `76`；
- 输出 `<<<AGENT2SCRIPT_ERROR>>> ... <<<END_AGENT2SCRIPT_ERROR>>>`；
- 错误中包含 `expected_output`、`actual_output` 和字段差异；
- 宿主必须把这个错误交回当前 Agent，让 Agent 按 expected_output 修正，再次进入校验。

Agent result 文件必须已经存在、是合法 JSON，并通过 `output.output_schema` 结构校验，否则同样禁止恢复。校验失败时会返回 `agent_result_validation_error`，其中包含 `output_schema`、`actual_result` 和具体字段差异；宿主应修正结果文件后重试 handoff。

通过校验后，handoff 执行器使用 workflow state 中保存的原始 `cwd` 执行 expected command，确保恢复尽可能发生在原工作目录与原启动上下文中。

**强制规则：宿主不得绕过 handoff 直接执行 Agent 自行返回的命令。** 否则 Looma 无法在执行前完成契约校验。

## 10. 固定 prompt

所有 Looma `script2agent.prompt` 必须逐字使用：

```text
通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；完成后仅按 expected_output 返回。
```

具体业务要求只能写入 `task`，脚本/运行时产物只能写入 `output`。

## 11. Replay 规则

Looma V0.1 使用 **same-command replay/resume**，不保存原始 Python 调用栈，也不拼接 Python 源代码。

因此：

- `step()` / `agent()` 的 replay-visible 调用顺序必须稳定；
- suspend 与 resume 之间不要修改会改变历史 event 顺序的代码；
- 跨边界值必须 JSON 可序列化，或能转换为 JSON；
- file handle、socket、thread、process、CUDA context、数据库连接不能直接作为持久化结果跨边界；
- replay 前发生的副作用必须放进 `step()`；
- 遇到 `ReplayMismatchError` 时检查代码路径和输入，不要手工篡改 history。

## 12. 循环

AEP 的核心能力之一是让 Agent 自然进入 Python Loop：

```python
@workflow
def repair(repo):
    for attempt in range(5):
        tests = step(run_tests, repo)

        review = agent(
            task="判断测试是否已经通过；未通过则给出修复方案。",
            input={"attempt": attempt, "tests": tests},
            output_schema=dict,
        )

        if review["done"]:
            return tests

        step(apply_fix, repo, review["fix"])
```

每一次 Agent 调用会形成独立 event。宿主 Agent 完成后执行同一原命令，Runtime 从入口 replay 并自然进入对应的下一轮。

## 13. 状态与调试

默认状态：

```text
.looma/
├── invocations/
└── runs/
    └── <run-id>/
        ├── state.json
        └── events/
```

查看运行列表：

```bash
looma status
```

查看最新 Workflow 的 event history、pending request、result path 和 expected_output：

```bash
looma inspect
```

查看指定 run：

```bash
looma inspect <run-id>
```

同一个启动命令需要多个独立逻辑实例时，为每个实例设置不同的：

```bash
LOOMA_RUN_KEY=job-a python main.py
LOOMA_RUN_KEY=job-b python main.py
```

同一个 `LOOMA_RUN_KEY` 表示同一个逻辑 active run；不同 key 彼此隔离。

清理：

```bash
looma reset --yes
```

查看当前安装包自带的 AEP Skill：

```bash
looma skill-path
```

## 14. 角色边界

**Python / Script：**

- 控制业务流程；
- 保存真实事实；
- 执行确定性动作；
- 管理循环条件、重试上限和可以确定性表达的验收门槛；
- 通过 `step()` 避免 replay 副作用。

**Host Coding Agent：**

- 分析；
- 判断；
- 规划；
- 使用宿主原生工具获取需要语义搜索或核验的真实证据；
- Review；
- 按宿主自身能力创建 / 调度 subagent；
- 在宿主内部执行并发任务并汇总；
- 写入结构化 Agent result；
- 按 `expected_output` 触发下一次脚本执行。

**Looma Runtime：**

- suspend；
- state；
- atomic durable JSON persistence；
- event history / inspect；
- replay；
- resume；
- `script2agent / agent2script` 边界。

## 15. 外部能力失败与真实数据 fallback

外部 SDK、API、网站或网络不可用时，可以把失败作为 Workflow 的正常分支处理，但不能为了继续流程而伪造事实。

推荐模式：

```text
step(): try provider / deterministic capability
        │
        ├─ success → continue
        │
        └─ recoverable failure
                ↓
             agent()
                ↓
      当前 Host 使用原生工具补充
                ↓
        sourced real evidence
                ↓
       step(): validate / accept
                │
                ├─ pass → continue
                └─ fail → retry / insufficient_evidence / fail
```

执行规则：

- `agent()` 仍然只把任务交回当前宿主，不得启动另一个 Coding Agent；
- Host 可以使用当前会话已有的 web/search/browser、终端、文件或其它原生工具取得真实信息；
- 外部事实应保留来源 URL、文件引用或其它可核验 provenance；
- 禁止编造、插值、估算或生成伪造业务事实来填补 live data 缺口；
- Agent 可以报告“证据不足”，不要为了满足 schema 而杜撰数据；
- 是否达到完成条件应尽可能由后续 Python validator / acceptance gate 决定，而不是只相信 Agent 自己声明 `done=true`；
- 达到有限重试次数后仍不足，应显式输出 `insufficient_evidence` 或失败；
- fixture/mock 可以用于 CI 测试控制流，但不能作为真实执行的业务证据。
## 16. 不要做什么

不要：

- 在 Looma Workflow 里重新创建一套 OpenAI/Anthropic LLM Client；
- 从 Looma / Workflow 中调用 Codex、Claude Code、SDW 的 CLI / SDK / API；
- 从 Looma / Workflow 中启动 subagent；
- 把 Looma 变成第二个宿主 Agent；
- 为每次 `agent()` 创建新的 resume 脚本；
- 把 Agent 业务结果放进 `agent2script`；
- 在 Agent 结果没有写入 `result_file` 前执行恢复命令；
- 把含有副作用的程序裸放在 replay 路径上；
- 把退出码 `75` 当作普通程序失败。

## 17. 核心心智模型

不要把：

```python
result = agent(...)
```

理解为：

```text
call LLM API
```

应该理解为：

```text
Program
  ↓
Suspend
  ↓
Host Agent reasons
  ↓
Result is persisted
  ↓
Same command
  ↓
Replay
  ↓
agent() returns
  ↓
Program continues
```

这就是 **Agent-Embedded Programming**。
