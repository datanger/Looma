# Looma

**Weave coding agents into ordinary Python control flow.**

Looma 是一个 replay-based Python runtime。它让 Codex、Claude Code、SDW 等宿主 coding agent 可以像普通函数一样参与 Python 工作流，同时底层仍保持 `script2agent -> agent2script -> script` 的程序化交接协议。

Looma 不直接连接任何 LLM API。模型、会话、工具权限和推理由宿主 coding agent 提供；Looma 只负责 Python 侧的 suspend、持久化、replay、resume 和边界协议。

```python
from dataclasses import dataclass
from looma import workflow, step, agent

@dataclass
class Decision:
    choice: str


def preprocess(data):
    return {"value": data * 2}


def run_a(x):
    return {"route": "A", "value": x["value"]}


def run_b(x):
    return {"route": "B", "value": x["value"]}


@workflow
def process(data):
    x = step(preprocess, data)

    decision = agent(
        task='分析输入并返回 JSON：{"choice": "A" | "B"}',
        input=x,
        output_schema=Decision,
    )

    if decision.choice == "A":
        return step(run_a, x)
    return step(run_b, x)


print(process(21))
```

## 核心思想

开发者看到的是普通 Python：

```text
step -> agent -> if/for/while -> step -> agent
```

Looma 底层执行的是：

```text
原 Python 命令
    ↓
@workflow
    ↓
step()             # 首次执行并持久化结果
    ↓
agent()
    ↓
script2agent
    ↓
当前进程 suspend / exit 75
    ↓
Codex / Claude Code / SDW
    ↓
写入 agent result JSON
    ↓
agent2script = 原 Python 启动命令
    ↓
重新执行同一命令
    ↓
Replay
    ↓
step() 命中历史结果
agent() 返回历史 agent 结果
    ↓
原 Python 控制流继续
```

因此 Resume 是 Looma Runtime 的内部概念。Agent 不需要知道 `resume.py`、workflow id、program counter 或 continuation id。

## 安装

开发版：

```bash
pip install -e .
```

构建 wheel：

```bash
python -m pip install build
python -m build --wheel
```

安装生成的 wheel：

```bash
pip install dist/looma_runtime-0.1.0-py3-none-any.whl
```

GitHub Actions 会在 Python 3.10 / 3.11 / 3.12 / 3.13 上运行测试，并生成 wheel artifact。

## 三个核心 API

### `@workflow`

定义可恢复的最外层 workflow。Looma 会根据 workflow 名称和原始命令定位当前 active run。

```python
@workflow
def main():
    ...
```

### `step()`

把有副作用、昂贵或不应在 replay 中重复执行的 Python 调用持久化。

```python
parsed = step(parse_large_file, path)
metrics = step(run_tests, repo)
```

第一次真正执行；之后 replay 直接返回之前保存的 JSON 结果。

### `agent()`

在普通 Python 控制流中插入一次宿主 Agent 调用。

```python
review = agent(
    task="分析测试结果并判断是否需要修改",
    input=test_result,
    output_schema=dict,
)
```

首次到达该调用时 Looma 生成 `script2agent` 并挂起；Agent 完成后重新执行原命令，Looma replay 到该位置并返回 Agent 结果。

## 为什么需要 `step()`

Looma V0.1 使用 replay，而不是保存真实 Python 调用栈。恢复时脚本会从入口重新执行，所以副作用必须被框架记录：

```python
# 不推荐：replay 会再次执行
write_database(data)
answer = agent(...)

# 推荐
step(write_database, data)
answer = agent(...)
```

纯计算、无副作用且成本很低的普通 Python 可以直接编写。

## 循环中的 Agent

普通 `for` / `while` 可以继续使用：

```python
@workflow
def optimize(config):
    for i in range(10):
        metrics = step(run_eval, config)

        decision = agent(
            task="判断是否结束；否则给出下一轮 config",
            input={"iteration": i, "metrics": metrics},
            output_schema=dict,
        )

        if decision["done"]:
            return metrics

        config = decision["next_config"]
```

每次 `agent()` 都形成一个独立 event。重新执行原命令后，Looma 按历史 event 顺序 replay 到正确的循环轮次。

## Agent 看到什么

Looma 保留两类边界对象：

```text
script2agent
agent2script
```

`script2agent` 包含：脚本来源、脚本输出 / Agent 输入、任务、固定 prompt，以及期望的 `agent2script`。

Agent 的业务结果写入 Looma 指定的 `result_file`。最终回复只需要：

```json
{
  "script": "/usr/bin/python3",
  "args": ["/project/main.py", "--input", "data.json"]
}
```

也就是重新运行原脚本命令。

## 本地状态

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

查看运行状态：

```bash
looma status
```

清理本地 workflow 状态：

```bash
looma reset --yes
```

查看随包安装的 coding-agent Skill：

```bash
looma skill-path
```

## Replay 约束

- `step()` / `agent()` 在 replay 中的调用顺序必须稳定。
- 已暂停的 workflow 恢复之前，不应修改会改变历史 event 顺序的代码。
- 跨 `step()` / `agent()` 边界的值必须可 JSON 序列化，或是 dataclass / Pydantic model / `Path`。
- file handle、socket、thread、process、CUDA context、数据库连接等运行时对象不能跨 replay 边界持久化。
- 文件写入、数据库写入、Shell/subprocess、网络调用、测试和昂贵计算建议放进 `step()`。

如果 replay 与已持久化历史不一致，Looma 会抛出 `ReplayMismatchError`，而不是静默恢复到错误位置。

## Skill

项目随包提供 `llm-driven-programmatic-coding` Skill：

```text
src/looma/skills/llm-driven-programmatic-coding/SKILL.md
```

该 Skill 面向 Codex / Claude Code / SDW 等 coding agent，说明如何识别 Looma workflow、如何处理 `script2agent`、如何写入 Agent 业务结果、如何返回 `agent2script`，以及 replay / step / loop 的编程约束。

## 当前阶段

V0.1 重点验证最小闭环：

```text
普通 Python
→ agent()
→ suspend
→ coding agent
→ same-command agent2script
→ replay
→ 原函数逻辑继续
```

后续计划包括并发 workflow、更完整的 history/inspect、失败重试策略、可插拔 state store、Agent host adapter 和更严格的 result schema 校验。
