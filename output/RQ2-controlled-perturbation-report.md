# RQ2 — 受控扰动实验报告：谁拥有「工具路由」

> ⚠️ **本报告的数字不可作为论文证据（2026-09-21 追加）。**
> 本实验的全部任务实例来自 `experiments/workloads/bounded_autonomy/scenarios.json`，**该场景集由我们自己撰写**（7 个自编场景）。按「任务数据必须来自公开 benchmark」的规则，下表的 ATSR、路由缺口、SLOC 增量等数字**不得进入论文结果表**。
>
> 仍然成立并可复用的是**实验装置与机制结论**：路由所有权的划分方式、验收闸门不泄露 oracle 的修复、widening 消融的设计、`ToolSession`/`RouteMissing` 的语义分离。数字部分已按公开数据重基，见
> [`research/RETRIEVAL_PERTURBATION_PROTOCOL.md`](../research/RETRIEVAL_PERTURBATION_PROTOCOL.md)（工作负载 `experiments/workloads/retrieval_perturbation/`，任务实例全部来自已钉版的 MuSiQue / HotpotQA / 2WikiMultiHopQA）。
>
> 下方的 0.25 → 1.00、+9/+4 SLOC 等具体数值，**只能作为装置自检记录阅读，不要引用**。

> **一句话结论**：在编排逻辑、驱动器与预算完全相同的条件下，把工具路由的所有权从「应用」换成「宿主 Agent」，使应用在留出集上的自适应成功率从 **0.25 提升到 1.00**，且在两个批次中使用**同一份文件、同一个命令**（SHA-256 相同，路由声明为空）。
>
> **这不是 Agent 质量结论**。本实验的「模型」是一个无 oracle 访问权限的确定性驱动器策略（`policy.py`），没有调用任何 LLM。它测量的是**路由灵活性与编排开销**。

---

## 1. 实验设计

四个编程范式，同一套扰动场景，同一个驱动器，同一个预算，**唯一变量是「谁决定存在哪些工具动作」**。

```
公开场景事实 →  应用编排  →  Result Contract / 验收闸门
                    │
                    ├─ 谁能发出哪些工具动作？（dev 批次冻结 / widened 批次补齐）
                    └─ 留出集让应用付出多少代价？
```

| 维度 | 设定 |
|---|---|
| 场景 | 7 个：dev 3 个（`normal`、`primary_tool_unavailable`、`conflicting_stale_note`），eval 4 个（见下表） |
| 驱动器 | `controlled/policy.py` 的 `AdaptiveDriverPolicy`，四范式共用，无 oracle |
| 预算 | 3 轮 × 每轮 12 个动作 |
| 工具面 | `ToolSession(scenario_id, allowed_actions)`；动作不在声明集时抛 `RouteMissing`，被记为**观测**而非崩溃 |
| 打分 | `validator.score_result`（实验侧打分，知道 oracle），与验收闸门 `validate_result` 严格分离 |

### 场景划分

| split | 场景 | 扰动内容 | 需要发现新源？ |
|---|---|---|---|
| dev | `normal` | 无 | 否 |
| dev | `primary_tool_unavailable` | 首选源不可用 | 否（镜像已在入口可见） |
| dev | `conflicting_stale_note` | 过期笔记与权威策略冲突 | 否 |
| eval | `renamed_authoritative_source` | 权威源改名 | **是** |
| eval | `missing_review_replaced_by_audit` | 评审缺失，等价审计记录在别的 id 下 | **是** |
| eval | `authoritative_only_after_discovery` | 入口点完全够不到权威源 | **是** |
| eval | `insufficient_after_adaptation` | **对照组**：不需要发现，正确答案就是 `insufficient` | 否 |

对照组是必要的：没有它，留出集里的每一次失败都等同于「需要发现的场景」，套件就会变成奖励「发现」而不是奖励「答对」。

### 两个批次

| 批次 | 含义 |
|---|---|
| `--routes dev` | 作者在 dev 划分后冻结下来的路由集 |
| `--routes widened` | 留出集实际需要的路由集 |

`route_declaration_delta_sloc = sloc(widened) − sloc(dev)` 就是这次「第二次修改」的代价。

---

## 2. 主表（本机实测）

**运行环境**：Python 3.10.12 · `Linux-6.8.0-138-generic-x86_64-with-glibc2.35` · commit `38b5e14ce6478cd0368d6a3e3a1d6a40c30865ba` · worktree dirty

```bash
PYTHONPATH=$PWD:$PWD/src python -m experiments.workloads.bounded_autonomy.controlled.run_controlled \
  --allow-missing-dependencies --output experiments/results/rq2-controlled.json
```

| 实现 | 批次 | ATSR dev | ATSR eval | eval 路由缺口 | 应用 SLOC | 路由增量 SLOC | 平均动作数 | 工具路径多样性 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Direct SDK | dev | 1.00 | **0.25** | 4（全部为 `list`） | 92 | 0 | 3.00 | 7 |
| Direct SDK | widened | 1.00 | **1.00** | 0 | 101 | +9 | 3.43 | 7 |
| LangGraph | dev | — | — | — | 189 | 0 | — | — |
| LangGraph | widened | — | — | — | 200 | +11 | — | — |
| MS Agent Framework | dev | — | — | — | 114 | 0 | — | — |
| MS Agent Framework | widened | — | — | — | 118 | +4 | — | — |
| **AEP / Looma** | dev | 1.00 | **1.00** | 0 | 110 | **0** | 3.43 | 7 |
| **AEP / Looma** | widened | 1.00 | **1.00** | 0 | 110 | **0** | 3.43 | 7 |

> **LangGraph 与 Microsoft Agent Framework 的行为列尚未测量。** 二者依赖
> `experiments/requirements-phase1.txt` 中钉住的 `langgraph==1.2.11` /
> `agent-framework-core==1.19.0`，本机无 pip、无外网，装不上，其行记录为
> `dependency_missing: true`。**表中只有它们的 SLOC 来自本机静态统计**。行为数字必须由
> `.github/workflows/research-autonomy.yml` 的 `controlled-comparison` job 产出
> （`research-results/rq2-controlled.json`）。这四个实现里我只**运行**过
> `direct_sdk`（两个批次）与 `looma`（两个批次，共 14 行 + 14 行 host 轨迹）。

### Looma 行的读法

- `declared_routes` 为空：结果 JSON 中 `application_declared_actions == []`——**应用不声明任何工具动作**，它只声明任务边界、Result Contract，以及 `step(validate_result)` 这个确定性闸门；
- Host 在 dev 与 widened 两个批次都给出 `read` + `list`，所以 `route_declaration_delta_sloc == 0`；
- `looma/workflow.py` 在两个批次**逐字节相同**，SHA-256 记录在结果 JSON 的
  `application_sha256` 里（测试 `test_aep_route_set_is_host_owned_and_the_application_is_unchanged` 断言两批次哈希相等）；
- `host_driver.py` 模拟外部宿主（Looma 的 `agent()` 那一侧），**不计入应用 SLOC**，单列为 `host_driver_sloc = 115`；
- **不要把它读成「AEP 代码更少」**：110 SLOC > Direct SDK 的 92 SLOC。这里的结论是**路由稳定性**，不是代码量。

### 逐场景（Direct SDK，dev 路由）

| 场景 | split | 成功 | 路由缺口 |
|---|---|:--:|---|
| `normal` | dev | ✅ | — |
| `primary_tool_unavailable` | dev | ✅ | — |
| `conflicting_stale_note` | dev | ✅ | — |
| `renamed_authoritative_source` | eval | ❌ | `list` |
| `missing_review_replaced_by_audit` | eval | ❌ | `list` |
| `authoritative_only_after_discovery` | eval | ❌ | `list` |
| `insufficient_after_adaptation` | eval | ✅ | `list` |

最后一行的行为值得单独注意：对照组「蒙对」了，但它**也**撞上了路由缺口。也就是说
`ATSR_eval = 0.25` 里那 1 分并非适应能力的体现——详情见 §5 的偏宽问题。

### 逐场景（Looma，两批次相同）

| 场景 | split | 宿主工具轨迹 |
|---|---|---|
| `normal` | dev | `read:policy-primary` → `read:review-R31` |
| `primary_tool_unavailable` | dev | `read:policy-primary` → `read:policy-mirror` → `read:review-R32` |
| `conflicting_stale_note` | dev | `read:policy-current` → `read:stale-note` → `read:review-R34` |
| `renamed_authoritative_source` | eval | `read:policy-primary` → `read:review-R33` → **`list`** → `read:regulatory-policy-v5` |
| `missing_review_replaced_by_audit` | eval | `read:policy-current` → `read:review-R35` → **`list`** → `read:audit-R35` |
| `authoritative_only_after_discovery` | eval | `read:community-note-R37` → `read:review-R37` → **`list`** → `read:policy-current-2026` |
| `insufficient_after_adaptation` | eval | `read:policy-current` → `read:score-R36` → `read:review-R36` → **`list`** |

四个 eval 场景的宿主轨迹里都出现了 `list`，且**应用侧零改动**。

---

## 3. 顺带修掉的一个真实效度漏洞：闸门反馈泄露 oracle

改之前，验收闸门的 `problems` 里含有 `decision mismatch: expected ...` 和 oracle 来源 id。而这些 problems 会作为 `previous_validation_problems` **回灌给 Agent 用于重试**——闸门等于在把答案递过去，而且对所有范式等量地抬高分数。

现在 `validator.py` 拆成两个函数：

| 函数 | 角色 | 允许知道什么 |
|---|---|---|
| `validate_result(scenario_id, result)` | **反馈安全的验收闸门** | 只允许公开可推导的事实：源 id 未知/不可用、来源数量不足、缺必需证据种类、缺权威源、decision 值非法 |
| `score_result(scenario_id, result)` | **实验侧打分** | `expected_decision`、`expected_supporting_source_ids`，并算出 `gate_ready / decision_correct / evidence_covered / task_success` |

`sanity.py` 新增 `gate_feedback_leaks_oracle` 诊断（当前 `false`），
`tests/test_bounded_autonomy.py` 用三个测试钉住：套件有判别力 / 反馈不泄露 oracle / 闸门与打分分离。

### sanity 诊断（同一环境）

| 诊断策略 | 成功率 |
|---|---:|
| 预定义静态路由 | 2 / 7（28.57%） |
| 自适应 oracle | 7 / 7（100%） |
| `gate_feedback_leaks_oracle` | `false` |

自适应 oracle 是确定性基准代码，不是 Host Agent；它只用来证明套件有判别力。

---

## 4. 复现

```bash
export PYTHONPATH=$PWD:$PWD/src
python -m pip install -e . pytest -r experiments/requirements-phase1.txt

# 全矩阵
python -m experiments.workloads.bounded_autonomy.controlled.run_controlled \
  --output experiments/results/rq2-controlled.json

# 只跑本机可运行的（跳过未安装的框架）
python -m experiments.workloads.bounded_autonomy.controlled.run_controlled \
  --paradigms direct_sdk,looma --routes dev,widened \
  --allow-missing-dependencies --output experiments/results/rq2-controlled.json

# 回归测试
python -m pytest tests/test_bounded_autonomy.py tests/test_bounded_autonomy_controlled.py
```

退出码：`0` 正常 · `2` harness 错误 · `3` 有框架未安装（加 `--allow-missing-dependencies` 可改为记为
`dependency_missing` 而不是失败）。`experiments/results/` 已被 gitignore；CI 写 `research-results/`。

本机（无 pip / 无 pytest）下，9 个测试（`tests/test_bounded_autonomy.py` 3 个 +
`tests/test_bounded_autonomy_controlled.py` 6 个）是我逐函数手工执行通过的，**pytest 本身从未在本机运行过**。

新增/变更文件：

- `experiments/workloads/bounded_autonomy/controlled/`：`protocol.py`、`policy.py`、`run_controlled.py`、
  `README.md`，以及 `direct_sdk/`、`langgraph/`、`microsoft_agent_framework/`、`looma/` 四个范式目录
  （各含 `workflow.py` / `widened.py` / `metadata.json`）
- `validator.py`（闸门/打分分离）、`sanity.py`（泄露诊断）、`scenarios.json`（7 场景 + dev/eval + 候选源）、
  `environment.py`（`split_of` / `scenarios_for_split` / `public_scenario.candidate_sources`）
- `tests/test_bounded_autonomy.py`（重写为 3 个）、`tests/test_bounded_autonomy_controlled.py`（新增 6 个）
- `.github/workflows/research-autonomy.yml`（`perturbation-sanity` + `controlled-comparison` 两个 job）
- 文档：`research/BOUNDED_AUTONOMY_PROTOCOL.md`、`research/INITIAL_RESULTS.md`、`controlled/README.md`

---

## 5. 已知威胁与未验证项（诚实清单）

**对结论的威胁**

1. **模型替身**。驱动器是确定性策略，不是模型，无 LLM 参与。本表只能支撑路由灵活性与编排开销的结论，
   不能支撑任何 Agent 输出质量结论。
2. **留出集的判别机制只有一条**。「能不能发现未通告的源」是 eval 划分唯一的区分轴；不可用/冲突这两条轴
   只出现在 dev 划分里。
3. **预算粒度是每轮而非全流程**，且重试维度几乎未被触发（当前所有行 `rounds == 1`）。
4. **闸门在 `insufficient` 分支偏宽**。`insufficient_after_adaptation` 场景下，「路由集耗尽」与
   「真的判断出证据不足」会得到同一个 `insufficient` 结果，闸门分不开这两种行为。所以这个场景不应在
   关于「适应质量」的论断里占权重；要收紧它，需要记录 Agent *为什么*停止，而当前边界不记录这个信息。

**未验证项（不要当成事实）**

- `langgraph` 与 `microsoft_agent_framework` 两个受控实现的**运行**从未执行过（本机无依赖），只做过静态检查与 SLOC 统计；
- LangGraph 在 `widened` 模式下新增节点 `discover`、以及 `path_map` 指向它的正确性未验证；
- Microsoft Agent Framework 受控版照抄了仓库中已跑通的 `@workflow` + `.build().run()` + `.get_outputs()` 写法，但受控版本本身未运行；
- 本机无 pytest，测试是逐函数手工执行通过的。

**下一步**

1. 由 CI 的 `controlled-comparison` job 补齐 LangGraph / MAF 的行为行（依赖已钉版本）；
2. 把重试维度真正激活（让某些场景需要跨轮次修正），否则「重试下的路由稳定性」这一维度未被检验；
3. 收紧 `insufficient` 分支，要求记录停止原因；
4. 论文级 RQ2 仍需用真实 Host Agent 跑未改动的
   `experiments/workloads/bounded_autonomy/workflow.py`，与模型驱动的动态 Agent/workflow 基线对比。

---

*数据源：`experiments/results/rq2-controlled.json`（本报告所有数字均取自该文件，未手工转抄）。*