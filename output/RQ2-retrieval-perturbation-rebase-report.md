# RQ2 扰动实验「公开数据重基」交付报告

**日期**：2026-09-21
**触发**：用户规则 —— 不能使用自建数据进行测试，任务数据必须来自认可度高的公开数据集。

---

## 1. 结论先行

RQ2 的自建场景数字已按公开数据重基，**装置复用、数字作废并重跑**。

| | 自建场景版（旧） | 公开数据版（新） |
|---|---|---|
| 任务实例 | 我们自撰的 7 个场景 | 已钉版 MuSiQue / HotpotQA / 2WikiMultiHopQA |
| 论文可用性 | ❌ 不可作为结果 | ✅ 数据 + 哈希 + 冻结子集可复现 |
| 装置 | `bounded_autonomy/controlled/` | `retrieval_perturbation/` |
| 本机可运行 | ✅ | ✅（fixture 控制流）／公开数据需 CI |
| 公开数字 | — | **待 CI，尚未产生** |

旧数字已在报告、`INITIAL_RESULTS.md`、`BOUNDED_AUTONOMY_PROTOCOL.md`、`PAPER_PLAN.md` 四处标注为**不可引用**。

---

## 2. 关键设计：区分「任务数据」与「实验装置」

这是整件事的核心。用户规则不能照字面一刀切，否则会把论文贡献一起删掉：

| | 必须来自公开 benchmark | 必须我们自己写 |
|---|---|---|
| 内容 | 题目、gold answer、语料段落、任务实例 | 扰动变换、工具面、验收闸门、评分器 |
| 本轮产物 | 钉版 HF revision + SHA-256 冻结子集 | `injectors.py` / `protocol.py` / `driver.py` |

**本实验没有撰写任何题目、答案或段落。** 已验证：对每一种扰动，可见语料的文本集合都是公开语料的**子集**（`test_perturbations_only_transform_public_chunks`）。

---

## 3. 六个扰动条件（全部是对公开数据的确定性变换）

| 条件 | 变换 | 对应 RQ2 扰动轴 | 划分 |
|---|---|---|---|
| `baseline` | 无 | 参照 | dev |
| `primary_tool_unavailable` | 环境撤下 `semantic_search` | 首选工具不可用 | dev |
| `source_id_renamed` | chunk id 全部重映射为不透明 id，检索只回 snippet | 预期来源缺失 | eval |
| `snippet_only` | 检索回 `(handle, snippet)`，handle→id 只能从 `list_chunks` 得到 | 需要额外验证 | eval |
| `evidence_withheld` | 语料截断为确定性 60% 子集，**可证明**移除了部分题目的 gold 证据 | 证据不足（负对照） | eval |
| `distractor_chunk` | 追加一条同一公开语料中的其它 chunk 作为竞争来源 | 来源冲突 | eval |

**唯一变量仍是「谁拥有工具路由」**：

- `direct_sdk`：应用声明路由 `semantic_search, keyword_search, read_chunk`；留出集需要 `list_chunks`（语料换 key 后，冻结路由再也无法把 handle 变成 chunk id）；
- `looma`：应用**不声明任何路由**，宿主拥有可达动作集，两个批次同一份文件。

---

## 4. 本机实测（fixture 语料，仅为装置自检，不是结果）

命令行：`python -m experiments.workloads.retrieval_perturbation.run_perturbation --data-root experiments/workloads/retrieval_perturbation/fixtures --datasets fixture` → exit 0，`mode: fixture`。

| 实现 | 批次 | 实例 | 可答 | dev 自适成功率 | **eval 自适成功率** | eval 路由缺口 | 应用 SLOC | 路由增量 SLOC | 应用 SHA-256 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| direct_sdk | dev | 36 | 27 | 1.00 | **0.3529** | 10（全为 `list_chunks`） | 114 | 0 | `43937acd` |
| direct_sdk | widened | 36 | 27 | 1.00 | **0.9412** | 0 | 130 | +16 | `196d92b8` |
| **looma** | dev | 36 | 27 | 1.00 | **0.9412** | 0 | 165 | **0** | `9d6fd86a` |
| **looma** | widened | 36 | 27 | 1.00 | **0.9412** | 0 | 165 | **0** | `9d6fd86a` |

`mode`: proxy 证据判定；`statuses`: complete / insufficient_evidence，harness error 0。

读法（三条都要一起读，缺一条都是误导）：

1. looma 两个批次**同一个 SHA-256、同样的结果**，路由增量 SLOC 为 0；direct_sdk 要改文件（+16 SLOC）才能把 eval 从 0.3529 拉到 0.9412。
2. **looma 的应用比 direct_sdk 大（165 vs 114 SLOC）。** 结论是**路由稳定**，不是代码更少。
3. eval 只到 0.9412 而非 1.00：加路由解决了「够不着」的问题，没有解决 `distractor_chunk` 的干扰问题。这是真实结果，不是瑕疵。
4. 负对照 `evidence_withheld` 上 `false_answers = 6`、`correct_refusal_rate = 0.333`：确定性驱动器在该拒绝时仍然作答。**负对照因此单独报告、不进入适应能力论断**。

---

## 5. 交付物

**新增工作负载** `experiments/workloads/retrieval_perturbation/`

| 文件 | 作用 |
|---|---|
| `corpus.py` | 按公开文件原形加载 `questions.json`/`chunks.json`，记录观测到的 schema 与文件摘要 |
| `injectors.py` | 六个确定性扰动 + 路由集定义 |
| `driver.py` | 确定性检索驱动器（受控模式的模型替身，无 gold 访问） |
| `protocol.py` | `RetrievalSession` 工具面、`RouteMissing`、边界闸门、实验侧评分 |
| `instance.py` | 实例构建；写出范式可读的 **gold-free** payload |
| `direct_sdk/` `looma/` | 两个对照实现（`looma/workflow.py` 为应用，`host_driver.py` 为宿主模拟器） |
| `fixtures/fixture/` | 公开文件原形的手写小语料，**仅用于控制流测试** |
| `README.md` | 运行方式与「不测什么」 |

**协议**：`research/RETRIEVAL_PERTURBATION_PROTOCOL.md`（含 6 条 threats to validity）
**CI**：`.github/workflows/research-retrieval-perturbation.yml` —— 先跑 fixture 控制流测试，再下载钉版公开数据、以 `--expect-public` 跑三个数据集、上传 `rq2-retrieval-perturbation.json`
**测试**：`tests/test_retrieval_perturbation.py`，13 个测试，本机全部 PASS（不 import 任何框架）

---

## 6. 防作弊与效度闸门（都可被测试击穿，不是声明）

- **payload 不含 gold 标签**：范式可读的实例文件只有公开语料与题目；无 `gold` 字段、无 gold 证据 id、无 original-id 映射。（注意：答案**可**由公开语料推得——那就是任务本身；泄露的是标签。）
- **闸门看不见 oracle**：`validate_result` 精确接受两个参数（result、持久化 session），测试用 `inspect.signature` 把它钉住；闸门反馈里断言不出现 gold answer、不出现 `expected` 字样，**同时**断言 Agent 自己那条错误引用必须被回报（过度净化会让重试失效）。
- **fixture 不能冒充结果**：`--expect-public` 会拒绝任何非钉版数据集名；fixture 运行额外写 `mode: fixture` + `fixture_warning`。CI 里专门有一个 job 断言这个拒绝行为。
- **自建场景数字不可引用**：四处文档已加注（见第 1 节表）。

---

## 7. 未验证 / 不能声称的

1. **公开数据上的数字尚未产生。** 本机无外网、无 pip、无 `huggingface_hub`，下载不了钉版语料；必须由 CI 执行。**不要在结果表里填任何未跑过的行。**
2. **不测答案质量。** 确定性驱动器无法做多跳推理，故 contain-match/EM/F1 在此工作负载上无意义。测的是公开 gold 证据在扰动下是否仍**可达**。
3. **语义检索在确定性装置里是词法排序的近似**（无嵌入索引）。本实验变化的是工具的**可得性**，不是排序质量；`primary_tool_unavailable` 因此是路由依赖测试，不是检索质量测试。
4. **证据存在性是代理量。** 公开记录未统一标注 supporting facts 时，用「gold answer 字符串出现在 chunk 文本中」判定，会高估；所以代理模式下门槛取「至少触及一条 gold 证据」，精确 id 模式取「全部触及」。二者在结果中标注 `evidence_mode`。
5. **`refused` 与「路由耗尽」不可区分** —— 已在 threats to validity 里写明，负对照因此不参与适应能力论断。
6. 未在本机跑过 `pytest`（本机没有 pytest），测试是逐函数 import 后手工调用验证的。

---

## 8. 下一步建议

1. **触发 CI**（`research-retrieval-perturbation.yml`），拿到公开数据上的第一版真实表格；同时确认 `research-arag-data.yml` 的冻结清单一致。
2. 若要在 RQ2 里保留「重试」维度：当前确定性驱动器基本单轮完成，`rounds` 维度仍未被真正检验。
3. 之后再谈 W3（τ-bench / ToolSandbox）—— 依赖与许可证核查需要联网，我本机做不了。