# Looma repository instructions

这是 Looma 的 Codex 标准仓库级指令文件。它同时承载 Runtime、Host Contract、Replay、示例约束与仓库开发规则；README 只保留项目定位、快速示例与安装方式。

---

## 1. Concept hierarchy

Looma 实现的是 **Agent-Embedded Programming（AEP，智能体嵌入式编程）**。

```text
Agent-Embedded Programming = 编程范式
Executable Skill           = AEP 的一种 Skill 封装形态
Looma                      = AEP 的一个 Python Runtime / Framework 实现
```

AEP 的核心职责分工：

```text
Program owns control flow and acceptance criteria
Agent owns semantic reasoning and evidence acquisition
Runtime owns continuity
```

也就是说：

- Python 负责 `if / for / while / function / exception`，以及可以确定性表达的完成条件、证据门槛和验收规则；
- 已经存在的 Host Coding Agent 负责理解、分析、判断、规划、Review、工具调用，以及需要语义能力的证据获取；
- Looma 负责 suspend、state、replay、resume 与边界校验。

Looma 不是第二个 Agent，也不是 LLM Client。

---

## 2. Host-native execution model

Looma 运行在已经存在的 Coding Agent 宿主环境中。

`agent(...)` 的语义不是：

```text
Looma → launch another Agent
```

而是：

```text
Current Host Agent
      │
      ├── starts / continues Python program
      │
      ▼
Program Runtime
      │
      ├── deterministic code
      │
      └── reaches agent(...)
              │
              ▼
         script2agent
              │
              ▼
Current Host Agent
      │
      ├── reasons
      ├── uses tools
      ├── may create native subagents
      ├── may execute independent work concurrently
      └── writes structured result
              │
              ▼
         guarded resume
              │
              ▼
Program Runtime
      │
      └── replay → agent() returns → continue
```

严格禁止把 Looma 实现成：

```text
Looma → codex CLI
Looma → Claude Code CLI
Looma → Agent SDK
Looma → LLM API
Looma → subprocess → another Agent
```

模型访问、会话、上下文、工具、终端、subagent 与并发策略全部属于 Host。

---

## 3. Public programming model

Looma 的公共编程模型只保留三个核心概念：

### `@workflow`

定义一个可恢复 Workflow：

```python
from looma import workflow

@workflow
def main(data):
    ...
```

Runtime 会记录当前 invocation 和 event history。

### `step()`

把有副作用、昂贵或不应在 replay 中重复执行的工作变成 durable step：

```python
parsed = step(parse_file, path)
tests = step(run_tests, repo)
```

第一次执行真正调用函数并保存 JSON-compatible 结果；replay 时返回历史结果。

典型用途：

- 文件 / 数据库写入；
- subprocess / shell；
- 测试；
- 网络请求；
- 大规模解析；
- 昂贵计算；
- 任何不能安全重复执行的副作用。

### `agent()`

定义宿主 Agent 边界：

```python
review = agent(
    task="分析结果并决定下一步。",
    input=result,
    output_schema=Review,
)
```

第一次到达这里时，Looma：

1. 生成 `script2agent`；
2. 持久化 request 与 workflow state；
3. 输出 request；
4. 以退出码 `75` 暂停当前 Python 进程。

宿主完成任务并恢复原命令后，Runtime replay 到同一位置，`agent()` 返回结构化业务结果。

---

## 4. Control handoff contracts

AEP 在 Looma 中有三个契约。

### Task Contract

程序告诉宿主：

```text
要完成什么任务
业务输入是什么
结果必须写到哪里
结果应该满足什么结构
```

Looma 用 `script2agent` 表达。

### Result Contract

宿主完成业务任务后，把业务结果写入：

```text
output.result_file
```

并满足：

```text
output.output_schema
```

业务结果不放进 `agent2script`。

### Resume Contract

`script2agent.expected_output` 表示允许恢复的唯一命令。

恢复前必须满足：

```text
actual.keys   == {"script", "args"}
actual.script == expected_output.script
actual.args   == expected_output.args
```

否则命令不得执行。

---

## 5. script2agent protocol

典型结构：

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
    "output_schema": {
      "type": "object"
    }
  },
  "task": "具体 Agent 任务。",
  "prompt": "固定协议文本",
  "expected_output": {
    "script": "/usr/bin/python3",
    "args": ["/project/main.py"]
  }
}
```

字段：

- `script`：产生本次交接的程序来源；
- `output.agent_input`：业务输入；
- `output.result_file`：Agent 最终结果文件；
- `output.output_schema`：结果约束；
- `task`：本次具体任务；
- `prompt`：固定交接说明；
- `expected_output`：允许恢复的命令。

固定 `prompt` 必须逐字保持：

```text
通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；完成后仅按 expected_output 返回。
```

具体业务要求只能进入 `task`。

---

## 6. agent2script protocol

Agent 完成业务任务后只返回：

```json
{
  "script": "...",
  "args": ["..."]
}
```

不包含：

```text
reasoning
business result
workflow state
context
next_action
resume id
```

默认情况下，这就是原始 Python 启动命令。

不要创建额外的 `resume.py`，也不要把 workflow id / continuation id 暴露给 Agent。

---

## 7. Guarded handoff

宿主应将 Agent 返回的 `agent2script` 保存为 JSON，然后调用：

```bash
looma handoff \
  --request <script2agent.json> \
  --response <agent2script.json>
```

Handoff 依次验证：

```text
Result Contract
    ↓
result_file exists
    ↓
valid JSON
    ↓
matches output_schema
    ↓
Resume Contract
    ↓
script + args exactly match expected_output
    ↓
execute original command
```

失败时返回退出码 `76`，并输出结构化：

```text
<<<AGENT2SCRIPT_ERROR>>>
...
<<<END_AGENT2SCRIPT_ERROR>>>
```

Result schema 不满足时使用 `agent_result_validation_error`。宿主应修正结果文件或 Agent 返回值后重新 handoff。

Runtime replay 还会再次校验结构化 Agent result，作为绕过 handoff 时的第二层保护。

---

## 8. Result schema validation

Looma 支持：

- built-in `dict / list / str / int / float / bool`；
- dataclass；
- Pydantic JSON Schema；
- 用户直接传入的 schema mapping。

结构校验覆盖当前边界所需要的 JSON Schema 子集，包括：

```text
object / array / string / integer / number / boolean / null
required
properties
additionalProperties
items
enum / const
anyOf / oneOf / allOf
local #/$defs references
basic min/max length and item count
```

例如：

```python
from dataclasses import dataclass

@dataclass
class Decision:
    choice: str
    score: int
```

会生成结构化 object schema，而不是只记录 Python 类型名。

---

## 9. Replay model

Looma 不保存真实 Python 调用栈，也不动态切割或拼接 Python 源码。

恢复方式：

```text
original command
      ↓
re-run program
      ↓
replay completed events
      ↓
return persisted values
      ↓
continue ordinary Python
```

因此：

- `step()` / `agent()` 的 replay-visible 调用顺序必须稳定；
- suspend 与 resume 之间不要修改会改变 event 路径的代码；
- 跨边界值必须 JSON-compatible；
- file handle、socket、thread、process、CUDA context、数据库连接等运行时对象不能直接跨边界保存；
- 副作用必须通过 `step()` 保护。

如果当前调用路径与历史不一致，抛出：

```text
ReplayMismatchError
```

Runtime 不会静默继续。

---

## 10. Durable state

默认目录：

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

状态文件使用同目录临时文件、`fsync` 和 atomic replace 写入，以降低进程中断导致部分写入的风险。

completed / failed run 会释放 active invocation pointer；历史 run 仍保留用于 inspect。

---

## 11. Workflow inspection

查看所有本地 run：

```bash
looma status
```

查看最新 run：

```bash
looma inspect
```

查看指定 run：

```bash
looma inspect <run-id>
```

Inspect 会显示：

- run id；
- workflow；
- status；
- invocation；
- optional run key；
- event history；
- pending request；
- result path；
- output schema；
- expected resume command；
- failure information。

这些是诊断信息，不需要进入 `agent2script`。

---

## 12. Independent workflow instances

默认情况下，一个 active run 由 workflow + command + cwd 识别。

相同命令需要多个独立逻辑实例时：

```bash
LOOMA_RUN_KEY=job-a python main.py
LOOMA_RUN_KEY=job-b python main.py
```

`LOOMA_RUN_KEY` 进入 invocation fingerprint：

- 不同 key → 独立 durable history；
- 相同 key → 同一个逻辑 active run。

这只是 Workflow instance isolation，不是 Agent concurrency。

---

## 13. Loops and branches

AEP 的一个核心价值是让 Agent 自然进入普通 Python 控制流：

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

每一次 Agent 调用形成独立 event。每次 resume 都从入口 replay，再自然回到正确的 loop iteration。

失败重试优先使用普通 Python：

```python
while ...:
    ...
```

不要在 Runtime 内隐藏一套通用 retry engine。

---

## 14. Concurrency and subagents

并发属于 Host Coding Agent。

Workflow 可以描述：

```python
result = agent(
    task="""
    检查 security、performance、tests 三个互相独立的方向。
    如果宿主支持 subagent，可以并发执行并最终汇总。
    """,
    input={"repo": "."},
    output_schema=ReviewResult,
)
```

Looma 的职责到这里结束。

宿主可以：

```text
Host Agent
   ├─ subagent A
   ├─ subagent B
   └─ subagent C
          ↓
        gather
          ↓
     one result_file
```

也可以顺序执行。

Workflow 的正确性不应依赖宿主一定支持 subagent 或某种并发 API。

---

## 15. Recoverable external-data fallback

外部 SDK、API、数据源或网络失败可以被建模为普通 Workflow 分支，但**失败不能成为伪造事实的理由**。

推荐模式：

```text
step(): try deterministic/provider capability
        │
        ├─ success → continue with real data
        │
        └─ recoverable failure
                ↓
             agent()
                ↓
      current Host uses native tools
                ↓
       sourced real evidence
                ↓
      step(): deterministic validation
                │
                ├─ accepted → continue
                └─ rejected → retry / insufficient_evidence / fail
```

规则：

- `step()` 可以把 package missing、DNS、provider unavailable 等失败转换成结构化结果，而不是隐藏错误；
- `agent()` 只能把任务交回**当前宿主 Agent**，由宿主使用已有的 web/search/browser、文件、终端或其它原生工具；
- Host 获取的外部事实应保留来源或其它可核验 provenance；
- 不得为了让 Workflow 继续而编造、插值、估算或生成伪造业务事实；
- Agent 可以判断证据，但是否满足业务完成条件应尽可能由后续 Python validator / acceptance gate 决定；
- 达到重试上限后证据仍不足时，应显式进入 `insufficient_evidence` 或失败状态，而不是伪装成正常成功；
- CI 可以使用 fixture/mock 验证控制流，但必须明确与 live evidence 分离，不能把测试数据当作真实业务结果。

这个模式是通用 AEP 设计原则，不依赖股票案例。
---

## 16. Executable Skill

Wheel 内置：

```text
src/looma/skills/
└── agent-embedded-programming/
    └── SKILL.md
```

查看安装后的 Skill：

```bash
looma skill-path
```

Skill 描述：

- AEP 语义；
- `@workflow / step / agent`；
- exit code `75`；
- `script2agent / agent2script`；
- Result / Resume Contract；
- host-native execution；
- loop / replay；
- handoff validation。

Executable Skill 是 AEP 的一种封装形态；Looma 是其 Python Runtime 实现之一。

---

## 17. Current scope and non-goals

当前 Looma 已实现：

```text
ordinary Python control flow
durable step
agent boundary
same-command replay/resume
multiple Agent calls
for / while / branching
integrated stock-analysis Agent with cross-script execution
AKShare-first market acquisition with sourced host-web fallback
recent-news research and evidence/analysis loops
deterministic evidence and analysis acceptance gates
complete / insufficient_evidence report status
host-native subagent concurrency task description
result schema validation
strict resume validation
workflow status / inspect
atomic durable-state writes
failed-run pointer cleanup
LOOMA_RUN_KEY instance isolation
wheel-packaged AEP Skill
```

当前明确不做：

```text
LLM client
Agent launcher
custom Agent spawn/join runtime
hidden generic retry engine
distributed scheduler/backend
pluggable state-store abstraction without a concrete use case
speculative Step primitives without replay-tested semantics
```

只有同时满足以下条件的新能力才应进入 Runtime：

```text
solves a real AEP use case
preserves the host-native boundary
has process-level automated tests
```

---

## 18. Repository development rules

修改 Looma 时必须遵守：

- Preserve the public programming model: `@workflow`, `step()`, `agent()`.
- Never launch Codex, Claude Code, SDW, another Agent process, or subagents from Looma through CLI / SDK / API / subprocess.
- Do not add direct LLM API dependencies.
- Preserve the exact fixed `script2agent.prompt`.
- Keep `agent2script` limited to exactly `script` and `args`.
- Treat `expected_output` as a strict Resume Contract.
- Validate `output.result_file` against `output.output_schema` before resume.
- Same-command resume must re-run the original Python invocation.
- Prefer deterministic replay and persisted events over source rewriting or raw stack restoration.
- Any replay-visible feature must include process restart/resume tests.
- Side-effectful work must be representable through `step()`.
- Durable state writes must remain atomic.
- Keep `LOOMA_RUN_KEY` instance semantics stable.
- The package must remain a pure Python wheel on Python 3.10+.
- Keep `src/looma/skills/agent-embedded-programming/SKILL.md` aligned with public behavior.
- When a live external-data fallback is used, require sourced real evidence; fixtures belong only to deterministic tests.
- Prefer program-owned acceptance gates over trusting an Agent self-declaration that work is complete.

---

## 19. Test expectations

CI currently covers Python:

```text
3.10
3.11
3.12
3.13
```

Regression coverage should include, where applicable:

- process restart / resume；
- step side-effect deduplication；
- loops and multiple Agent calls；
- integrated stock-analysis Agent：AKShare-first acquisition + sourced host fallback + news research + evidence/analysis gates + multiple Agent boundaries；
- invalid result schema rejection；
- invalid `agent2script` rejection；
- direct-resume defense；
- workflow inspect；
- run isolation；
- failed-run cleanup；
- wheel install and CLI smoke tests；
- packaged AEP Skill。

A Runtime feature is not complete until its restart/replay semantics are tested.

---

## 20. Related docs

- `README.md` — project overview and quick start
- `docs/agent-embedded-programming.md` — AEP paradigm
- `docs/design.md` — runtime design
- `examples/stock_analysis_agent/README.md` — the single integrated example: AKShare-first market acquisition + sourced host fallback + evidence gates + host-native subagent concurrency
- `src/looma/skills/agent-embedded-programming/SKILL.md` — host-facing executable Skill
