# 技术文档：ACP 审片预算收紧与 Prompt/权限加固

> **背景案例**：项目 `7bed327a-f272-4887-a294-938d30b98723`、generation `edcae35e-1184-47d4-8b4e-735c79851580`（variant `high_conversion`）。六个 HF 分镜走 Cursor ACP author，`generating_material` 阶段约 100 分钟；单 slot wall 28–66 分钟，vision 审片合计 68 次，而每镜 preview 仅约 6 秒。  
> **文档用途**：记录问题根因、已确认的优化方案与具体改法，供实施前对齐与事后复盘；读者无需先读完整代码 diff。  
> **关联计划**：[`docs/superpowers/plans/2026-07-04-material-gate-finalize-plan.md`](../superpowers/plans/2026-07-04-material-gate-finalize-plan.md)（review 用尽 → 仍出片 + 人工 gate）

---

## 1. 我们在解决什么问题

### 1.1 用户可感知的现象

| 现象 | 典型数据（edcae35e） |
|------|----------------------|
| 每个分镜只做几秒钟 preview，却要几十分钟 | slot-5 wall ≈ 66 min，HF 渲染 ≈ 25s |
| 审片（vision）次数远多于预期 | 68 次 `video_understanding`，slot-5 单独 14 次 |
| Cursor 大量读仓库源码 | 单 session `Read File` 104 次、`grep` 36 次 |
| 多数 slot 审片结论为 `review_unavailable`，仅 slot-6 完整通过 | AgentRunLog schema 漂移导致 in-session review 失败循环 |

### 1.2 问题归类

1. **成本与轮次模型不合理**：lint 修复与 vision 审片共用 `VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS`，计划中的 `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS` 未落地。  
2. **基础设施错误被当成「创意未过」**：`tokenUsage.total` 字段校验失败 → 反复 repair → 反复 vision。  
3. **外部 agent 权限过大 + prompt 自相矛盾**：工作目录在 repo 根、follow-up 暴露栈 trace、MCP 要求 agent 先 review 才能 write → 驱使 Cursor 读 `handlers.py` 等实现代码。  
4. **概念混淆**：「worker turn」「lint 次数」「review 次数」「ReAct turn」混用，难以配置和复盘。

---

## 2. 根因分析（当前实现）

### 2.1 ACP 会话里实际发生了什么

外部 ACP（Cursor）与内部 ReAct 是两套模型：

```text
外部 ACP（当前）：
  Worker 发一次 prompt → Cursor 跑完 → Worker harvest spec
    → Worker 再 lint → Worker 再 vision review
  任一环节失败 → Worker 再发 follow-up prompt（计为 turn+1）

内部 ReAct（当前）：
  循环：LLM 想一轮 → 可连续调多个 MCP 工具 → 再看结果想下一轮
  lint 是工具返回值；上限是 VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS（默认 12）
```

edcae35e 中 slot-5 的时间结构（observability 汇总）：

- Cursor agent 思考/读代码/调工具：约 38 min  
- Worker vision 审片：约 28 min（14 次 × ~2 min）  
- HF preview 渲染：< 1 min  

**瓶颈不在 6 秒视频编码，而在 ACP 会话 + vision 审片。**

### 2.2 为什么审片次数会到 10–14 次/slot

理论上限曾是 `ACP_MAX_TURNS(5) × SESSION_RETRY(1) = 10` 次 worker 侧 review，但 slot-5 出现 14 次，原因包括：

- 同一 observability run 内 session 因 `Connection closed` retry，又跑满多轮 worker follow-up。  
- 每次 follow-up 在 lint 通过后都会触发 post-turn review。  
- 基础设施失败未 waive 时，review 失败 → repair follow-up → 再 review，直到 turn 或 session 用尽。  
- 文档中的 `MATERIAL_REVIEW_MAX_ROUNDS` **代码未实现**，无法单独 cap vision。

### 2.3 成功路径其实不会「打满 5 次 review」

若 lint 一次过、review 一次过、无 infra 错误，worker 会在第一次 review 通过后 **立刻 break**，vision 仅 **1 次**。  
edcae35e 的高次数是 **失败循环**，不是成功路径的设计意图。

### 2.4 为什么 Cursor 会读源码

| 因素 | 说明 |
|------|------|
| `cwd=repo_root` | Cursor 默认可浏览整个 VideoMaker 仓库 |
| MCP review gate | `VM_ACP_IN_SESSION_REVIEW=true` 时，`write_material_spec` 必须先有 review marker；agent 调 review 失败后会去读 MCP/worker 实现 |
| follow-up 原文 | `Invalid AgentRunLog payload…` 等栈信息出现在 repair prompt 里，诱发「调试基础设施」行为 |
| prompt 暴露路径 | `--repo-root D:\VideoMaker`、完整 lint shell 命令写在 task instructions 里 |
| 软约束 | prompt 写「禁止探索源码」，但 `HeadlessCompositionClient` 的 `FsBridge` 只限制 ACP 协议读写，**不限制** Cursor 自带 Read/grep/Shell |

完整会话 trace 在：

```text
storage/projects/{projectId}/logs/composition-author/acp/{runId}/
  session.json / prompt.json / tool_calls.jsonl / outcome.json
```

---

## 3. 设计决策（已确认）

### 3.1 核心原则：Review-Only 预算

经过讨论，放弃「lint turn 与 review turn 双计数器（原方案 A）」，改为：

1. **Lint 只是 agent 工具**  
   在 ACP 会话内通过 MCP `composition_lint_draft` 自循环（与 `skill_view` 相同），工具返回错误 → agent 改 spec → 再 lint，**不单独占 review 额度**。

2. **Worker 只对 vision 审片计次**  
   `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS=2` 是每个分镜 author 过程的主成本上限（按实际发起 vision 计数；同 specHash 缓存命中、基础设施 waive 不计）。

3. **Worker follow-up 仍可能存在**（ACP 协议限制）  
   agent 交卷后，worker 仍需 harvest → 最终 lint 校验 → review。缺 spec 或 lint 失败时 worker 会再发 prompt，但这 **不消耗 review 额度**，也不在 follow-up 文案里引导 agent 去调 review。

4. **Review 额度用尽**  
   接受当前 spec，写入 `approved=false` 的 marker，进入人工 material gate（与 material-gate-finalize 计划一致），**不把整个 slot 判为 hard fail**。

5. **废弃 lint-turn 产品语义**  
   `VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS` 标记 deprecated，仅作 `VIDEOMAKER_COMPOSITION_ACP_DIALOGUE_SAFETY_MAX`（默认 15）的兼容 fallback，用于防止 worker↔agent 对话死循环，**不表示「lint 最多 N 次」**。

### 3.2 MCP 与 Worker 审片解耦

| 层 | 变更 |
|----|------|
| MCP 子进程 | 固定 `VM_ACP_IN_SESSION_REVIEW=false` → agent 写 spec **不需要** review marker |
| Worker | `_acp_in_session_review_enabled()` 仍为 true 时，**仅 worker** 在交卷后做 post-turn vision |
| Agent 工作流 | `skill_view → composition_lint_draft（校内循环）→ write_material_spec`；禁止 agent 调 `review_material_preview` |

这样可避免 agent 侧重复 vision，也避免 agent 为搞懂 write gate 去读 Python 源码。

### 3.3 Prompt / Spawn 权限收紧

| 措施 | 目的 |
|------|------|
| `spawn` / `new_session` 的 `cwd=scratch_dir` | 缩小 Cursor 默认可见目录 |
| 新增 `prompt_sanitize.py` | follow-up 错误脱敏，去掉 AgentRunLog/绝对路径/`.py` 栈 |
| task instructions 去掉 repo 绝对路径与 shell lint 命令 | Cursor 只用 MCP lint |
| bootstrap ACP 文案分 Phase A/B | A：校内 lint 交卷；B：worker review 反馈只改画面，禁止查实现 |

可选：`VIDEOMAKER_ACP_SPAWN_CWD=scratch|repo`（默认 scratch，便于本地调试回退）。

### 3.4 内部 ReAct 如何对齐

ReAct **不受** `ACP_MAX_TURNS` / `DIALOGUE_SAFETY_MAX` 影响。

| 概念 | ReAct 含义 |
|------|------------|
| 一次 turn | 一次 `complete_with_tools()`（material_author LLM 推理一轮） |
| 同一 turn 内多个 tool | 例如 4 次 `skill_view` + 1 次 lint → **仍算 1 turn** |
| `REACT_MAX_TURNS`（默认 12） | LLM 编排轮次上限，防死循环；与 vision 预算 **正交** |
| `MATERIAL_REVIEW_MAX_ROUNDS` | 在 `CompositionToolExecutor.review_material_preview` 工具层 enforce（ReAct 无 worker post-turn review） |

业界惯例：tool-agent 几乎都有 step/recursion 硬上限（LangGraph `recursion_limit`、LangChain `max_iterations` 等），再配合 timeout。保留 `REACT_MAX_TURNS` 合理；composition 复杂 slot 若 telemetry 显示常触顶，可酌情调至 16–20。

### 3.5 目标链路（改后）

```text
┌─ Agent 会话（MCP，不计 review 次数）──────────────────────┐
│  读 skill → 起草 MaterialSpec → lint 工具循环直到通过      │
│  → write_material_spec 交卷                                 │
└───────────────────────────┬────────────────────────────────┘
                            ▼
┌─ Worker 验收（仅此处计 vision 次数）────────────────────────┐
│  收 spec → 最终 lint 校验（失败则发 lint follow-up，不扣 review）│
│  → 若尚无 approved marker：render preview + material_reviewer │
│     （最多 MATERIAL_REVIEW_MAX_ROUNDS 次有效 vision）        │
│  → 创意未过：发 review follow-up；额度用尽：marker 失败 + 人工 gate │
│  → 基础设施错误：waive，不计入 review 次数                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 具体实现方式

### 4.1 新增/调整的环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS` | `2` | 每 slot author 有效 vision 审片上限 |
| `VIDEOMAKER_COMPOSITION_ACP_DIALOGUE_SAFETY_MAX` | `15` | ACP worker↔agent 对话轮次安全阀（非 lint 预算） |
| `VIDEOMAKER_ACP_SPAWN_CWD` | `scratch` | Cursor 进程工作目录 |
| `VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS` | `12`（文档可建议 16） | ReAct LLM 编排上限 |
| `VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS` | — | **deprecated**，fallback 到 DIALOGUE_SAFETY_MAX |

### 4.2 代码改动清单

| 模块 | 文件 | 改动要点 |
|------|------|----------|
| 审片配置 | `services/worker/app/pipelines/material_review.py` | 新增 `material_review_max_rounds()` |
| ACP 主循环 | `services/worker/app/composition/acp/author.py` | 引入 `dialogue_round` + `review_rounds_used`；lint follow-up 不扣 review；review 用尽 break；MCP env 固定 `VM_ACP_IN_SESSION_REVIEW=false`；spawn cwd |
| Prompt 脱敏 | `services/worker/app/composition/acp/prompt_sanitize.py` | **新建**；sanitize follow-up 错误 |
| Bootstrap | `services/composition/composition/skills/bootstrap.py` | ACP Phase A/B 文案 |
| Task 说明 | `author.py` `_build_acp_task_instructions` | 去掉 repo 路径与 shell lint；明确 worker 独占 review |
| ReAct 工具 | `services/composition/composition/author/tools.py` | `review_material_preview` 受 max rounds 约束 |
| 可观测性 | `services/worker/app/observability/acp_author_recorder.py` | metadata 增加 `dialogueRound`、`reviewRound`、`skippedReason` |
| 配置示例 | `services/api/.env.example`、`AGENTS.md` | 同步 env 说明 |
| 计划文档 | `docs/superpowers/plans/2026-07-04-material-gate-finalize-plan.md` | § In-session 轮次改为 review-only 已实现 |

### 4.3 ACP 循环伪代码（实现参考）

```python
dialogue_round = 0
review_rounds_used = 0

while True:
    dialogue_round += 1
    if dialogue_round > acp_dialogue_safety_max():
        raise SessionFailed("dialogue safety exceeded")

    await conn.prompt(system + user)  # 受 prompt_timeout 约束
    spec = harvest_spec()
    if spec is None:
        user = lint_followup_sanitized(["missing spec"])
        continue  # 不扣 review

    lint_errors = lint_spec_after_turn(spec)
    if lint_errors:
        user = lint_followup_sanitized(lint_errors)  # 不含 review 步骤
        continue  # 不扣 review

    if marker_approved(spec):
        break

    if review_rounds_used >= material_review_max_rounds():
        write_marker(failed, reason="review_rounds_exhausted")
        break  # 接受 spec，人工 gate

    report, errors = review_spec_after_turn(spec)
    if infra_waived(errors):
        break  # 不计 review_rounds_used

    review_rounds_used += 1

    if report.approved:
        break

    if review_rounds_used >= material_review_max_rounds():
        write_marker(failed, report)
        break

    user = review_followup_sanitized(report)
```

### 4.4 测试要求

**Worker（`services/worker/tests/test_acp_author.py`）**

- lint follow-up 多次后成功 → vision 仅 1 次  
- review 拒绝 1 次后通过 → vision 2 次  
- review 用尽 → 仍返回 spec，marker `approved=false`，无第 3 次 vision  
- lint follow-up 不增加 `review_rounds_used`  
- MCP 环境 `VM_ACP_IN_SESSION_REVIEW=false` 且 worker review 仍执行  
- follow-up 不含 `review_material_preview` 引导；无 AgentRunLog 栈  

**Composition（`tests/test_react_agent.py`、MCP tests）**

- 第 3 次 `review_material_preview` tool 被拒绝或 skipped  

### 4.5 验证命令

```powershell
cd services/worker
python -m pytest tests/test_acp_author.py tests/test_material_review_infrastructure.py -q
python -m compileall app

cd services/composition
python -m pytest tests/test_react_agent.py tests/test_mcp_material_review_tools.py -q
```

**E2E 期望**：一次 HF 生成中，每个 slot 的 `logs/model-calls` 里 `video_understanding` ≤ 2；成功路径 = 1；`tool_calls.jsonl` 中 Read 次数相对 edcae35e 明显下降。

---

## 5. 与已有修复的关系

本会话早些时候已定位、**可能已在工作区但未 commit** 的修复，与本方案互补：

| 修复 | 作用 |
|------|------|
| AgentRunLog `tokenUsage` 归一化 | 减少 infra 误判为 hard gate |
| ACP store 路径 / `VM_DATABASE_PATH` 注入 | 减少 review 降级为 text_only |
| contracts schema 补 `specHash` 等 | 避免 in-session review 写 report 失败 |

**本方案**从架构上减少「infra 失败 → 无限 repair → 无限 vision」的概率；schema 修复仍需保留。

---

## 6. 明确不在本次范围

- Cursor CLI 原生禁用 Read/grep 工具（无稳定 API）  
- 将 skills 复制到 scratch 的 bundle（若 cwd 隔离后仍读源码，可 follow-up）  
- material-gate-finalize 完整 finalize 管线（仅对齐 review 用尽语义）  
- 取消 `REACT_MAX_TURNS`（保留为 LLM 安全阀）

---

## 7. 预期效果（如何衡量成功）

| 指标 | 改前（edcae35e 量级） | 改后目标 |
|------|----------------------|----------|
| 每 slot vision 次数 | 6–14 | ≤ 2（成功路径 1） |
| 单 slot wall（HF 分镜） | 28–66 min | 显著下降（视 Cursor 行为而定） |
| ACP trace Read/grep | 100+ / session | 明显减少 |
| lint 修复能力 | 有，但与 review 共用 turn | 保留，且不消耗 review 额度 |
| 人工 gate | 多数 review_unavailable | review 用尽仍出 preview，可 override 批准 |

---

## 8. 参考资料

- 会话 trace 示例：`storage/projects/7bed327a-…/logs/composition-author/acp/6c2b51ffac0a/`（slot-5 长会话）  
- 早期 ACP review 超时复盘：[`2026-07-01-acp-internal-error-material-review-video-timeout-session.md`](2026-07-01-acp-internal-error-material-review-video-timeout-session.md)  
- Material gate 职责：[`2026-07-04-material-gate-finalize-revise-session.md`](2026-07-04-material-gate-finalize-revise-session.md)  
- 实施 checklist（执行时用）：Cursor plan `acp-review-only-budget`（仓库外 `.cursor/plans/`）

---

*文档版本：2026-07-06；状态：待实施（代码改动尚未合并）。*
