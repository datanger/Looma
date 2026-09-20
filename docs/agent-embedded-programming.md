# Agent-Embedded Programming (AEP)

**Agent-Embedded Programming（智能体嵌入式编程）** 是 Looma 正式采用的编程范式名称。

## 定义

AEP 把宿主 Coding Agent 视作一种可暂停、可恢复的智能计算单元，并把它直接嵌入普通程序控制流。

与直接调用 LLM API 不同，AEP 不要求业务 Workflow 自己维护 Model Client、API Key、Endpoint、Session 或 Agent Loop。模型能力由宿主 Coding Agent 提供，程序只表达何时需要智能判断以及如何消费结果。

```python
result = step(run_tests, repo)

review = agent(
    task="判断结果是否满足目标，未满足则给出下一步。",
    input=result,
    input_schema={"type": "object"},
    output_schema=Review,
)

if review.done:
    return result
```

## 三层模型

```text
Agent-Embedded Programming
    编程范式
        │
        ▼
Executable Skill
    Skill 封装形式
        │
        ▼
Looma
    Python Runtime / Framework
```

## 与传统 Skill 的区别

传统 Skill 主要描述：

```text
instructions
knowledge
SOP
tool guidance
```

AEP 下的 Executable Skill 还能够描述和依赖：

```text
Python control flow
loop
state
step
agent boundary
suspend
replay
resume
```

因此 Skill 不再只告诉 Agent “怎么做”，而可以参与一个真实可执行、可恢复的程序过程。

## 与传统 LLM Workflow Framework 的区别

典型 LLM Workflow Framework：

```text
Application
→ Agent Framework
→ LLM SDK
→ Model API
```

AEP / Looma：

```text
Python Program
→ Looma Runtime
→ script2agent
→ Existing Coding Agent Host
→ agent2script
→ same Python command
→ replay / continue
```

AEP 复用宿主 Agent 已有的：

- 模型访问；
- 会话；
- 上下文；
- 工具；
- Shell；
- 文件系统；
- Agent Loop。

Looma 不再重复创建第二套模型接入层。

## 核心原则

1. **Program owns control flow and acceptance criteria.** Python 拥有业务控制流、循环，以及可以确定性表达的完成条件与验收门槛。
2. **Agent owns semantic reasoning and evidence acquisition.** Agent 负责非确定性语义判断，以及需要宿主工具完成的搜索、核验和证据获取。
3. **Runtime owns continuity.** Looma 负责 suspend / state / replay / resume。
4. **Boundary stays small.** Agent 与 Script 只通过 script2agent / agent2script 交接。
5. **No duplicate LLM client.** Workflow 不重复配置 LLM API。
6. **Same command resumes.** 默认恢复动作重新执行原始 Python invocation，而不是暴露内部 resume script。
7. **Evidence must remain real.** 外部能力失败时可以交给当前宿主补充真实、可核验的证据，但不能用伪造数据让流程继续。
8. **Boundary inputs can be contracted.** `input_schema` 可在 suspend 前阻止结构错误输入进入 Agent 边界，并成为 replay-visible contract。
9. **Completion is a program decision where possible.** Agent 提供语义结果；是否满足完成条件，应尽可能由 Python validation / acceptance gate 决定。

## AEP 的目标

最终，调用 Agent 应该像调用普通函数一样自然：

```python
decision = agent(...)
```

但它可以跨越：

```text
process exit
agent execution
persistent state
process restart
replay
```

并在逻辑上返回到原程序位置继续运行。

这就是 Agent-Embedded Programming。

## 外部能力失败也是普通控制流

AEP 不要求外部 SDK、API 或数据源永远可用。程序可以先通过 `step()` 尝试确定性能力；发生可恢复失败后，通过 `agent()` 把补充研究交回当前宿主，再由普通 Python 校验是否接受结果。

```text
provider step
    │
    ├─ success → continue
    └─ failure → current Host gathers sourced evidence
                         ↓
                  deterministic validation
                         ↓
              continue / retry / insufficient
```

关键约束是：Host 使用的是自己的原生工具，Looma 不创建第二个 Agent；live evidence 必须可核验，fixture/mock 只属于测试；如果证据不足，程序应该显式表达不足，而不是伪装成成功。

## Contract-Guarded Agent Boundary

AEP 可以把一次智能计算边界表示为：

```text
B = (T, I, O, R, A)
```

其中：

- `T`：Task Contract；
- `I`：可选 `input_schema` + 经过规范化的 Agent input；
- `O`：`output_schema` + result file；
- `R`：必须严格匹配的 Resume Contract；
- `A`：业务程序自己的 deterministic acceptance gate。

Agent 可以在边界内部自主选择推理和工具路径，但输入、结果与程序恢复都必须跨过确定性的程序契约。
