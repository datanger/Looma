---
name: llm-driven-programmatic-coding
description: 使用 Looma Runtime 将 Codex、Claude Code、SDW 等宿主 coding agent 与 Python 脚本、函数、类组成可循环、可恢复的程序化工作流；不单独配置或直连 LLM API。底层保持 script2agent / agent2script 两类交接协议，上层通过 @workflow、step()、agent() 以接近普通 Python 的方式编写。
---

# 大模型驱动的程序化编程

## 1. 技能目标

本技能用于构建由 coding agent 与确定性 Python 程序协作完成的程序化工作流。

- **agent**：由 Codex、Claude Code、SDW 等宿主 coding agent 执行，负责分析、判断、规划、生成、修改、复核等非确定性语义任务。
- **script**：由 Python 脚本、函数或类执行，负责读取、解析、计算、写文件、测试、固定规则和确定性流程。
- **runtime**：由 `looma-runtime` 提供，负责 workflow 状态、suspend、replay、resume、step 结果缓存和 agent 调用结果恢复。
- **不单独配置 LLM API**：API Key、Endpoint、模型 SDK、会话管理和工具权限均由 coding agent 宿主环境负责。

本框架的目标是让业务代码保持接近普通 Python：

```python
from looma import workflow, step, agent

@workflow
def process(data):
    parsed = step(parse_data, data)
    decision = agent(
        task="判断下一步采用 A 还是 B",
        input=parsed,
        output_schema=dict,
    )
    if decision["choice"] == "A":
        return step(run_a, parsed)
    return step(run_b, parsed)
```

开发者不需要手工处理 workflow id、resume script、checkpoint 或 Codex session。

---

## 2. 核心运行机制

Looma 使用 **same-command replay/resume**。

第一次执行原命令：

```text
python main.py --input data.json
```

运行到 `agent(...)` 时：

```text
普通 Python
  ↓
step(...)              # 首次执行并缓存结果
  ↓
agent(...)
  ↓
生成 script2agent
  ↓
保存 workflow state
  ↓
当前 Python 进程退出，等待宿主 agent
```

宿主 agent 完成任务后：

1. 将业务结果写入 `script2agent.output.result_file` 指定的 JSON 文件；
2. 最后仅返回 `expected_output` 指定的 `agent2script`；
3. `expected_output` 默认就是原来的 Python 启动命令。

因此 agent2script 类似：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py", "--input", "data.json"]
}
```

执行器再次运行同一命令后，Runtime 从函数入口 replay：

```text
step(...)   → 命中历史结果，不重复副作用
agent(...)  → 发现 result_file，直接返回 agent 业务结果
后续 if / for / while / 函数继续正常执行
```

**Resume 是 Runtime 的内部概念，不暴露给 agent。** Agent 无需知道 `resume_workflow.py`、program counter 或 continuation id。

---

## 3. 三个核心 Python API

### 3.1 `@workflow`

最外层可恢复函数：

```python
@workflow
def main(data):
    ...
```

职责：

- 创建或恢复 workflow run；
- 捕获原始 Python invocation；
- 管理 replay event 顺序；
- 捕获 agent suspend；
- workflow 正常完成后关闭 active run。

### 3.2 `step()`

用于确定性、昂贵或有副作用的 Python 操作：

```python
parsed = step(parse_docx, "input.docx")
metrics = step(run_tests, repo_path)
```

第一次执行真正调用函数，并保存 JSON 结果；replay 时直接返回历史结果，不再次执行函数。

以下操作应优先包在 `step()` 中：

- 写文件；
- 数据库写入；
- Shell / subprocess；
- 测试执行；
- 网络调用；
- 大规模解析或计算；
- 任何不能安全重复执行的副作用。

纯计算且重复执行无副作用的普通 Python 可以不包 `step()`。

### 3.3 `agent()`

用于需要宿主 coding agent 进行语义判断的位置：

```python
review = agent(
    task="Review 测试结果并判断是否需要修复",
    input=test_result,
    output_schema=ReviewResult,
)
```

从业务代码看，它像普通同步函数；实际首次执行会 suspend，后续 replay 才返回 agent 结果。

`output_schema` 支持：

- `dict/list/str/int/float/bool`；
- dataclass；
- Pydantic Model（如果业务项目已安装 Pydantic）；
- JSON Schema dict；
- `None`（任意 JSON）。

---

## 4. Replay 编程规则

Runtime 不保存真实 Python 调用栈，也不拼接 Python 源代码，而是重新运行原脚本并重放已完成 event。

因此必须遵守：

1. `step()` / `agent()` 在 replay 中的调用顺序必须确定；
2. 已挂起 workflow 恢复前，不修改会影响 event 顺序的代码；
3. 跨 agent 边界的数据必须可 JSON 序列化；
4. file handle、socket、thread、process、CUDA context、数据库连接等运行时对象不得跨边界持久化；需要在新的 step 内重新创建；
5. 有副作用的代码不要裸写在 `agent()` 之前，否则 replay 会再次执行；应使用 `step()`；
6. `for` / `while` 可以正常使用，只要其路径由已持久化的输入、step 结果和 agent 结果确定。

例如循环：

```python
@workflow
def optimize(config):
    for i in range(10):
        metrics = step(run_eval, config)
        decision = agent(
            task="判断是否结束；否则给出下一轮 config",
            input={"iteration": i, "metrics": metrics},
            output_schema=Decision,
        )
        if decision.done:
            return metrics
        config = decision.next_config
```

每次 `agent()` 都形成独立 event；Agent 完成后执行同一原命令，Runtime replay 到对应循环轮次后继续。

---

## 5. 仅两类需要规范化的交接

`task_type` 只用于描述需要跨 Agent / Script 边界的交接，合法值仍只有：

```text
agent2script | script2agent
```

纯 agent 内部任务和纯 script 内部任务不使用交接对象。

| task_type | 执行关系 | 限制对象 |
| --- | --- | --- |
| `agent2script` | agent 完成后发起或执行 script | 限制 agent 最终输出，只返回 `script` 和 `args` |
| `script2agent` | script / function / class 产生数据后交给 agent | 限制交给 agent 的对象格式 |

---

## 6. `agent2script`：只允许脚本和参数

格式：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py", "--input", "data.json"]
}
```

约束：

- `script` 必须来自允许执行的程序；
- `args` 必须是参数数组，不能是拼接 Shell 字符串；
- 不允许管道、重定向、命令替换、后台执行或未授权参数；
- 不包含业务结果、上下文、reasoning、workflow id 或 resume id；
- Looma 默认将 `expected_output` 生成为当前 workflow 的原 Python invocation，使恢复命令与原命令保持一致。

业务结果由 agent 写入 `script2agent.output.result_file`，不通过 `agent2script` 携带。

---

## 7. `script2agent`：输入事实 + Agent 任务 + 期待恢复命令

格式：

```json
{
  "script": {
    "path": "/project/main.py",
    "function": "process",
    "class": null
  },
  "output": {
    "agent_input": {
      "files": ["src/a.py", "tests/test_a.py"],
      "issue": "空输入时发生 IndexError"
    },
    "result_file": "/project/.looma/runs/.../0002-agent-result.json",
    "output_schema": {
      "type": "object"
    }
  },
  "task": "定位根因并输出结构化结果。运行时要求会说明将结果写入 result_file。",
  "prompt": "通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；完成后仅按 expected_output 返回。",
  "expected_output": {
    "script": "/usr/bin/python3",
    "args": ["/project/main.py"]
  }
}
```

字段说明：

- `script`：产生交接输入的原脚本及 workflow 函数来源；
- `output.agent_input`：`agent()` 的业务输入；
- `output.result_file`：agent 必须写入的业务结果 JSON；
- `output.output_schema`：result JSON 约束；
- `task`：具体 Agent 任务 + Runtime 写结果要求；
- `prompt`：固定协议说明；
- `expected_output`：完成后必须返回的 `agent2script`，默认就是原脚本 invocation。

---

## 8. `prompt` 唯一固定模板（强制）

所有 `script2agent` 对象的 `prompt` 必须逐字使用：

```text
通用说明：script 表示产生输入数据的脚本来源；output 表示脚本实际产生的数据或产物路径；task 表示需要完成的具体任务；prompt 表示本通用说明；expected_output 表示 agent 完成后期待返回的 agent2script 输出格式。请先理解各字段，再执行 task；如果信息不足，明确指出缺失信息；完成后仅按 expected_output 返回。
```

不得翻译、改写、扩展、删减、插值或拼接其它内容。所有具体业务内容写入 `task` 或 `output`。

---

## 9. 宿主 coding agent 的标准执行方式

当脚本以退出码 `75` 暂停，并输出 `<<<SCRIPT2AGENT>>> ... <<<END_SCRIPT2AGENT>>>` 时：

1. 读取 `script2agent`；
2. 理解 `script`、`output`、`task`、`prompt`、`expected_output`；
3. 执行 `task`；
4. 将最终业务结果以 UTF-8 JSON 写入 `output.result_file`；
5. 校验结果符合 `output.output_schema`；
6. 最后仅返回 `expected_output` 中的：

```json
{
  "script": "...",
  "args": ["..."]
}
```

7. 执行该命令；Runtime 会自动恢复原 workflow。

如果脚本再次暂停，重复上述步骤；如果退出码为 `0`，workflow 完成。

---

## 10. 典型：代码修改 → 测试 → Agent 判断 → 再测试

```python
from looma import agent, step, workflow

@workflow
def fix_issue(repo):
    context = step(collect_context, repo)

    plan = agent(
        task="分析问题并给出修改计划",
        input=context,
        output_schema=dict,
    )

    patch_result = step(apply_patch, repo, plan)
    test_result = step(run_tests, repo)

    review = agent(
        task="根据测试结果判断是否完成；未完成则给出下一轮修复建议",
        input={"patch": patch_result, "tests": test_result},
        output_schema=dict,
    )

    if review["done"]:
        return review

    return step(apply_patch, repo, review["fix"])
```

复杂的持续修复应使用显式 `while` / `for` Loop，让 Python 程序拥有循环控制权，agent 只是循环中的可暂停调用。

---

## 11. 状态和调试

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

明确需要从头开始时：

```bash
looma reset --yes
```

不要在 workflow 正等待 Agent 时手工删除单个 event 文件，否则会破坏 replay history。

---

## 12. 适用与不适用场景

适合：

- Coding / test / review 多轮闭环；
- 法规解析 → Agent 判断 → 确定性写入；
- 数据处理 → Agent 审核 → 再处理；
- Python `for` / `while` 中间需要 Codex/SDW 做语义判断；
- 不希望单独接 LLM API，但宿主 Coding Agent 已有模型能力；
- 希望 Agent 完成后重新执行原脚本并透明恢复。

当前 V0.1 不适合：

- 同一 workflow + 完全相同命令行的多实例并发；
- 需要持久化 file handle/socket/GPU context 等不可序列化运行时对象；
- 代码在 suspend 与 resume 之间发生影响 replay event 顺序的大幅修改；
- 强分布式、多机器、高可用调度（后续可在 Runtime 上增加 durable backend）。

---

## 13. 设计原则

- **Agent 做语义决策，Script 做确定性执行。**
- **Python 拥有业务流程和循环控制权。**
- **宿主 Agent 拥有 LLM、会话、工具和权限。**
- **Runtime 拥有 suspend / replay / resume / state。**
- **交接协议保持极简；运行时状态不污染 agent2script。**
- **恢复默认重新执行原脚本，而不是暴露专用 resume 命令。**

---

## 14. 安装与项目接入

安装 wheel：

```bash
pip install looma_runtime-0.1.0-py3-none-any.whl
```

源码开发：

```bash
pip install -e .
```

查询安装后的 Skill 路径：

```bash
looma skill-path
```

业务项目最小接入：

```python
from looma import workflow, step, agent

@workflow
def main(input_path: str):
    parsed = step(parse_file, input_path)
    review = agent(
        task="检查解析结果并返回结构化判断",
        input=parsed,
        output_schema=dict,
    )
    return step(write_result, review)
```

第一次运行如果遇到 `agent()`，脚本会以退出码 `75` 暂停。此时宿主 coding agent 应处理 stdout 中的 `SCRIPT2AGENT` 对象，写入 `result_file`，再执行 `expected_output` 中的原命令。重复这一过程，直到脚本正常退出 `0`。

---

## 15. 宿主 Agent 不应该做什么

处理 Looma workflow 时，不要：

- 自己发明新的 resume 命令；
- 把业务结果塞进 `agent2script`；
- 修改 `expected_output` 以绕过原脚本；
- 在没有写入 `output.result_file` 前执行恢复命令；
- 将 `script` 与 `args` 拼成未经校验的 Shell 字符串；
- 直接操作 `.looma` 内部 state 来模拟完成；
- 因为看到退出码 `75` 就当成普通程序失败。

退出码 `75` 在 Looma 中表示：**workflow 已持久化并正在等待 Agent。**

---

## 16. 判断是否应使用 `agent()` 或 `step()`

使用 `agent()`，当任务需要：

- 语义理解；
- 方案判断；
- 代码分析；
- Review；
- 规划；
- 根据非结构化信息作出结构化决策。

使用 `step()`，当任务需要：

- 运行 Python 函数；
- 解析文件；
- 写入文件；
- 执行测试；
- 调用 subprocess；
- 数据库或网络副作用；
- 任何希望 replay 时“不再重复执行”的操作。

如果只是便宜、纯粹、确定性的内存计算，可以直接使用普通 Python，不必包装。

---

## 17. 处理失败

如果 Agent 无法完成 `task`：

1. 不要伪造一个满足 schema 的结果；
2. 明确说明缺失信息或失败原因；
3. 不要写入错误的 `result_file`；
4. 不要执行 `expected_output`，避免 Runtime 把未完成调用当作可恢复调用继续执行。

如果 Agent 已经写入结果但恢复后 Looma 报 `ReplayMismatchError`，通常表示 suspend 与 resume 之间代码路径发生改变，或 `step()` / `agent()` 调用顺序发生变化。优先检查代码和输入，不要手工篡改 event history。
