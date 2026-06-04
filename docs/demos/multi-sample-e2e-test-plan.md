# 多样例分析与结构合成 — 端到端测试方案

**功能范围**：多文件 upload-batch、并行 analyze-batch、Primary + References 样例选择、`structure_synthesizer` 结构合成、Generation Run 历史与 Provenance 展示。

**关联实现**：`docs/superpowers/plans/2026-06-04-multi-sample-analysis-plan.md`

**快速勾选版**：见 [§6 测试清单](#6-测试清单勾选)

---

## 1. 测试目标与范围

### 1.1 目标

验证从「多样例上传 → 并行分析 → 样例选择 → 结构合成 → 双变体生成 → Run 历史 / Provenance 展示」的完整闭环，并覆盖自动推荐、手动 override、失败与恢复路径。

### 1.2 在测范围内

| 模块 | 能力 |
|------|------|
| Contracts | `UploadBatch`、`ProjectSampleSelection`、`SampleRecommendation`、`StructureProvenance`、`GenerationRun` |
| API | upload-batch、analyze-batch、selection CRUD、recommend/reset、generation-runs、generation-plan + `generationRunId` |
| Worker | `structure_synthesizer`、产物 `synthesized-structure.json` / `structure-provenance.json` |
| Web | 多上传、样例选择（视频预览）、批次分析进度、生成历史、Provenance 面板 |
| 存储 | SQLite 新表/列、磁盘 artifact 路径 |

### 1.3 不在本次 E2E 范围（可记为后续项）

- `sample_selector` Agent 独立 rerank（未实现）
- 合成 checkpoint `synthesizing_structure` resume 细测（未单独持久化 stage）
- Run 级单次合成、多 variant 共享（当前为 per-generation 合成）
- Web vitest 全绿（Windows 临时目录 EPERM 时需换 basetemp）

---

## 2. 测试策略

### 2.1 三档路径

| 档位 | 用途 | 配置要点 |
|------|------|----------|
| **自动化回归** | PR / 合并前 | pytest + typecheck + contracts validate |
| **Fixture E2E** | 无模型 Key、流程冒烟 | `VIDEOMAKER_FIXTURE_MODE=true` |
| **Live E2E** | 真实合成与演示验收 | `VIDEOMAKER_FIXTURE_MODE=false` + Model Gateway 已配置 |

### 2.2 推荐执行顺序

```text
自动化预检（§3）
  → 环境启动（§4）
  → 场景 A–C：上传 / 分析 / 自动选择
  → 场景 D：手动 primary + references
  → 场景 E–G：合成生成 / Run 历史 / Provenance
  → 场景 H–J：异常、刷新、Fixture fallback
  → 磁盘与 API 抽检（§5）
  → 清单勾选（§6）
```

**预计耗时**：自动化 5–10 分钟；Fixture 手动 25–40 分钟；Live 手动 45–90 分钟（视样例分析与生视频耗时）。

---

## 3. 自动化预检（必须通过）

在手动 E2E 前执行：

```powershell
cd d:\VideoMaker\packages\contracts
npm run check
npm run validate:schemas

cd d:\VideoMaker\services\api
python -m pytest tests/test_sample_selection_routes.py tests/test_p0_flow_routes.py tests/test_multi_variant_generation.py -q --basetemp=d:\VideoMaker\.pytest-tmp

cd d:\VideoMaker\services\worker
python -m pytest tests/test_structure_synthesizer_agent.py -q --basetemp=d:\VideoMaker\.pytest-tmp

cd d:\VideoMaker\apps\web
npm run typecheck
```

| 检查项 | 通过标准 |
|--------|----------|
| Contracts | 无 TS / schema 校验错误 |
| API pytest | 27+ 项全绿（含 selection、batch、partial_failed run） |
| Worker pytest | synthesizer 单测通过 |
| Web typecheck | 无 TS 错误 |

---

## 4. 环境准备

### 4.1 启动服务

**终端 1 — API + Worker**

```powershell
cd d:\VideoMaker\services\api
# Fixture 冒烟
$env:VIDEOMAKER_FIXTURE_MODE = "true"
# Live 验收时改为 "false"

# 多样例相关（可选，默认值如下）
$env:VIDEOMAKER_MAX_CONCURRENT_SAMPLE_ANALYSIS = "2"
$env:VIDEOMAKER_MAX_REFERENCE_SAMPLES = "4"
$env:VIDEOMAKER_SAMPLE_BATCH_GAP_MIN = "30"

.\run-dev.ps1
```

**终端 2 — Web**

```powershell
cd d:\VideoMaker\apps\web
# .env.local
# VIDEOMAKER_API_URL=http://127.0.0.1:8000
# VIDEOMAKER_USE_FIXTURE_FALLBACK=false
npm run dev
```

浏览器：`http://localhost:3000/projects`

### 4.2 预检 API

```http
GET http://127.0.0.1:8000/health
```

期望：`{ "ok": true }`

### 4.3 Live 模式额外准备

- 工作台 **模型服务** 至少配置 **text** provider（结构合成 Agent 需要）
- 准备 **2–3 个短 mp4**（建议 5–30 秒，便于快速分析）
- Brief + 至少 1 张图片素材（走完整 generation 链路）

---

## 5. 数据与磁盘验证参考

### 5.1 API 路由速查

| 方法 | 路径 |
|------|------|
| POST | `/api/projects/{id}/samples/upload-batch` |
| POST | `/api/projects/{id}/samples/analyze-batch` |
| GET | `/api/projects/{id}/upload-batches` |
| POST | `/api/projects/{id}/samples/recommend` |
| GET/PUT | `/api/projects/{id}/samples/selection` |
| POST | `/api/projects/{id}/samples/selection/reset` |
| GET | `/api/projects/{id}/generation-runs` |
| GET | `/api/projects/{id}/generation-runs/{runId}` |
| POST | `/api/projects/{id}/generation-plan`（返回 `generationRunId`） |

### 5.2 磁盘路径（`storage/projects/{projectId}/`）

```text
samples/{sampleId}/source.mp4
samples/{sampleId}/analysis/video-structure.json
generations/{generationId}/synthesized-structure.json    # 有 reference 时
generations/{generationId}/structure-provenance.json     # 有 reference 且合成成功时
```

### 5.3 SQLite 表

- `upload_batches`
- `project_sample_selection`
- `generation_runs`
- `samples.upload_batch_id`
- `generations.generation_run_id`

---

## 6. 测试清单（勾选）

### 6.1 自动化回归

- [ ] `packages/contracts` check + validate:schemas 通过
- [ ] `services/api` selection + p0 flow + multi-variant pytest 通过
- [ ] `services/worker` structure_synthesizer pytest 通过
- [ ] `apps/web` typecheck 通过

### 6.2 场景 A：多文件 upload-batch

**步骤**

1. 新建或打开项目，进入工作台 **样例视频** 面板
2. 本地上传 **2–3 个 mp4**（一次多选）
3. 观察上传成功提示与批次 ID

**期望**

- [ ] UI 显示「已上传 N 个样例（批次 xxx）」
- [ ] `GET .../upload-batches` 返回 1 条 batch，`status` 为 `uploading`（尚未分析完成前）
- [ ] 每个 sample 有 `uploadBatchId`，列表可视频预览（非裸 UUID）
- [ ] 磁盘 `storage/projects/{id}/samples/{sampleId}/source.*` 均存在

**API 抽检（可选）**

```powershell
curl http://127.0.0.1:8000/api/projects/{projectId}/upload-batches
```

---

### 6.3 场景 B：analyze-batch 并行分析

**步骤**

1. 点击 **分析当前批次**（或调用 analyze-batch API）
2. 打开 **进度** 面板，观察多样例并行任务
3. 等待全部终端态（succeeded / failed）

**期望**

- [ ] `POST .../samples/analyze-batch` 返回 `tasks[]` 与 `maxConcurrent`
- [ ] 超出并发上限时，样例先为 `queued`，运行中为 `analyzing`
- [ ] 各样例 SSE/轮询 task 独立，互不覆盖 taskId
- [ ] 全部成功后 batch `status` → `complete`；部分失败 → `partial_failed`
- [ ] 成功样例 `hasStructure=true`，分析 Tab 可查看结构

**API 抽检**

```http
POST /api/projects/{id}/samples/analyze-batch
Content-Type: application/json

{"uploadBatchId": "<batchId>"}
```

---

### 6.4 场景 C：自动样例选择（auto）

**前置**：场景 B 至少 **2 个样例已分析成功**（同 upload-batch）

**步骤**

1. 打开 **样例选择** 面板
2. 确认模式 badge 为 **自动**
3. 阅读面板顶部「自动规则」说明

**期望**

- [ ] 主样例为当前批次内**已分析**样例（通常 batch 内第一个已分析）
- [ ] 主样例 / 候选展示 **视频预览** 与文件名，非仅 UUID
- [ ] `GET .../samples/selection` 返回 `mode: "auto"`、`primarySampleId`、`activeUploadBatchId`
- [ ] `POST .../samples/recommend` 的 `candidates` 为**当前批次内全部样例**（含未分析），非「仅已分析」
- [ ] 展开「全部样例」列出项目内所有样例，当前批次有「当前批次」标记

**虚拟批次（可选高级用例）**

1. 不用 upload-batch，间隔 **>30 分钟** 分两次单文件上传（或调 `VIDEOMAKER_SAMPLE_BATCH_GAP_MIN=1` 缩短间隔后测）
2. 确认 recommend 以**最新时间窗**内样例为候选

---

### 6.5 场景 D：手动 primary + references（user_override）

**前置**：≥2 个已分析样例

**步骤**

1. 展开全部样例，将样例 A **设为主样例**
2. 将样例 B **加入参考**（可再选 C 作第二参考）
3. 确认模式变为 **手动**
4. 点击 **恢复自动推荐**，再确认回到 auto

**期望**

- [ ] `PUT .../samples/selection` 后 `mode: "user_override"`
- [ ] 参考样例区域展示视频卡片（非 ID 列表）
- [ ] 未分析样例可设为主样例，但生成时应被前端拦截或 API 400（需先分析）
- [ ] `POST .../samples/selection/reset` 恢复推荐 primary/references

**API 抽检**

```http
PUT /api/projects/{id}/samples/selection
Content-Type: application/json

{
  "primarySampleId": "<sampleA>",
  "referenceSampleIds": ["<sampleB>"]
}
```

---

### 6.6 场景 E：带 references 的 generation + 结构合成

**前置**：场景 D 已设 primary + ≥1 reference；Brief 与素材已保存

**Fixture 模式步骤**

1. 点击 **生成计划**（默认双变体）
2. 观察进度 → 结果 Tab
3. 查看 **生成历史** 与 **结构合成溯源**（若有 reference）

**期望**

- [ ] `POST .../generation-plan` 响应含 `generationRunId` 与 2 条 `generations`
- [ ] SQLite `generation_runs` 新增 1 行，`generation_ids_json` 含 2 个 id
- [ ] 各 generation 的 `generation_run_id` 外键正确
- [ ] Fixture 下：合成走 primary fallback，仍写入 `synthesized-structure.json` / `structure-provenance.json`（有 reference 时）
- [ ] Run 完成后 `GET .../generation-runs/{runId}` 的 `status` 为 `completed` 或 `partial_failed`
- [ ] 有 artifact 时 `provenanceId` / `synthesizedStructureId` 与磁盘一致；无 artifact 时 `provenanceId` 为 null

**Live 模式额外期望**

- [ ] Worker 日志出现 `synthesizing_structure` stage
- [ ] `structure-provenance.json` 中 `slotAttribution` 非空
- [ ] 合成结构 `id` 形如 `synthesized-{runId}`

**磁盘检查**

```powershell
Get-ChildItem d:\VideoMaker\storage\projects\{projectId}\generations\{generationId}\
# 应含 synthesized-structure.json、structure-provenance.json（有 reference 时）
```

---

### 6.7 场景 F：Generation Run 历史

**步骤**

1. 对同一项目执行 **第二次** 生成（可改 brief 或 selection 后生成）
2. 打开 **结果** Tab → **生成历史**
3. 点击较早 run 的 **查看**

**期望**

- [ ] `GET .../generation-runs` 按时间倒序 ≥2 条
- [ ] 切换 run 不覆盖另一 run 的 generation 记录（不同 `generationRunId`）
- [ ] 选中 run 后加载对应 variant plan / gap（首个 generation 的 plan）
- [ ] session 刷新页面后 `activeGenerationRunId` 仍可恢复（sessionStorage）

---

### 6.8 场景 G：Provenance UI

**前置**：场景 E 已成功且含 reference

**步骤**

1. 生成全部完成后，切到 **分析** Tab
2. 切到 **结果** Tab

**期望**

- [ ] 生成完成后 **自动** 拉取 provenance（无需手动点「查看」）
- [ ] **分析** Tab 与 **结果** Tab 均可见「结构合成溯源」折叠面板
- [ ] 面板展示主样例 ID、参考数量、槽位归因列表（可展开）
- [ ] `GET .../generation-runs/{runId}` 响应含 `provenance` 对象（与磁盘 JSON 一致）

---

### 6.9 场景 H：异常与边界

| 子场景 | 操作 | 期望 |
|--------|------|------|
| H1 部分 variant 失败 | Live 下故意让一生图/生成失败（或 MixedResultPipeline 自动化已覆盖） | Run `status=partial_failed`；至少一 variant succeeded |
| H2 无 reference 生成 | selection 仅 primary，references 为空 | 不写入 provenance；run 无 `provenanceId` |
| H3 分析失败样例 | 上传损坏文件或中断分析 | sample `failed`；batch 可 `partial_failed`；未分析不可作 reference |
| H4 并发分析 | 同 batch 4+ 样例，`MAX_CONCURRENT=2` | 同时 running ≤2；其余先 `queued` |
| H5 生成前校验 | primary 未分析时点生成 | 前端提示「请先对主样例完成分析」 |

---

### 6.10 场景 I：页面刷新与任务恢复

- [ ] 分析进行中刷新 → 批次进度 / task 可恢复
- [ ] 生成进行中刷新 → 多 task 进度恢复
- [ ] 生成完成后刷新 → `GET .../generations/latest` 与 generation-runs 仍正确
- [ ] selection 手动 override 刷新后仍保持（SQLite 权威）

---

### 6.11 场景 J：Fixture fallback（Web）

**步骤**

1. 停止 API，设置 `VIDEOMAKER_USE_FIXTURE_FALLBACK=true`
2. 打开项目页，触发 upload-batch / selection / generation-runs 相关 UI

**期望**

- [ ] `fixture-resolver` 对新路由返回合理 mock，页面不白屏
- [ ] generation-plan mock 含 `generationRunId`

---

## 7. API 端到端脚本（可选）

将 `{projectId}`、`{batchId}` 替换为实际值：

```powershell
$base = "http://127.0.0.1:8000"
$pid = "<projectId>"

# 1. 推荐与选择
Invoke-RestMethod "$base/api/projects/$pid/samples/recommend" -Method Post
Invoke-RestMethod "$base/api/projects/$pid/samples/selection"

# 2. 批次列表
Invoke-RestMethod "$base/api/projects/$pid/upload-batches"

# 3. 生成（需已分析 primary）
$body = @{
  variants = @("high_click")
  sampleSelection = @{
    primarySampleId = "<primarySampleId>"
    referenceSampleIds = @("<refSampleId>")
  }
} | ConvertTo-Json -Depth 5
$plan = Invoke-RestMethod "$base/api/projects/$pid/generation-plan" -Method Post -Body $body -ContentType "application/json"
$runId = $plan.generationRunId

# 4. Run 详情（生成完成后）
Invoke-RestMethod "$base/api/projects/$pid/generation-runs/$runId"
```

---

## 8. 验收通过标准（Sign-off）

满足以下全部条件可标记本功能 **E2E 通过**：

1. **§3 自动化预检** 全部绿色
2. **场景 A–G** 在 Fixture 模式下手动勾选完成
3. **场景 E + G** 在 Live 模式下至少完成 1 次（含 reference 合成 + provenance 展示）
4. **场景 H1、H2、H5** 至少各验证 1 次
5. 磁盘与 `generation_runs` 表抽检无 orphan / 错误 `provenanceId`
6. 无 P0 回归：单样例上传、单样例分析、双变体生成、latest generation 加载仍正常

---

## 9. 缺陷记录模板

| ID | 场景 | 复现步骤 | 期望 | 实际 | 严重程度 | 备注 |
|----|------|----------|------|------|----------|------|
| MS-001 | | | | | P0/P1/P2 | |

---

## 10. 参考文档

- 架构与路由：`AGENTS.md`
- 实现计划：`docs/superpowers/plans/2026-06-04-multi-sample-analysis-plan.md`
- P0/P1 底座：`docs/demos/p0-demo-checklist.md`、`docs/demos/p1-manual-test-guide.md`
