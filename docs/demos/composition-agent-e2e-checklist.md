# HyperFrames Agent Composition E2E Checklist

本清单覆盖 **CompositionEngine / HyperFrames Agent（分镜 material author）** 与 **Composition Pattern Promote（动效入库）** 两类能力。

## 测试范围说明（请先读）

| 层级 | 名称 | 覆盖什么 | 不覆盖什么 |
|------|------|----------|------------|
| **A** | 模块自动化（pytest / vitest） | `services/composition`、`services/worker` HF material、`services/api` promote 路由、`apps/web` Promote 面板；HF CLI + `CompositionEngine` build/lint/render 逻辑 | 不创建真实项目、不跑完整 generation 流水线 |
| **B** | HF 管线冒烟（无 LLM） | 手填 `MaterialSpec` → build → lint → render → 真实 MP4 | 不调用 ReAct Agent、不写 storyboard |
| **C** | Agent 单点（需 text provider） | `author_material_spec`（single_shot / react）→ render 单 slot clip | 不跑 sample 分析、不全片 FFmpeg 合成 |
| **D** | Workbench 全链路 E2E | 项目 → 样片/ brief → generation → HF material completion → 成片 MP4 → Promote 入库 | 耗时长；依赖 API + Worker + Web + 模型配额 |

**「阶段 1 全量自动化」= 层级 A（+ 可选 B）**，不是从项目创建到成片 MP4 的完整业务 E2E。完整业务闭环见 **层级 D**。

---

## Prerequisites

- Node.js >= 22, FFmpeg on PATH
- Repo root: `npm install` + `npm run hyperframes:doctor`（FFmpeg / Chrome 通过即可；Docker 可选）
- `skills/public/hyperframes/SKILL.md` present
- `skills/private/videomaker-composition/SKILL.md` present
- Worker env: `VIDEOMAKER_COMPOSITION_MODE=hybrid`（default）
- **Live Agent / live Promote：** Workbench 已配置 **text provider**（baseUrl + model + API key）
- **CI / 无 LLM：** `VIDEOMAKER_FIXTURE_MODE=true`（promote prepare 与部分 agent 测试）

### 常用 env

| Env | 含义 | 默认 |
|-----|------|------|
| `VIDEOMAKER_COMPOSITION_MODE` | `hybrid` 或 `legacy` | `hybrid` |
| `VIDEOMAKER_COMPOSITION_AGENT_MODE` | `react` / `single_shot` / `legacy` | `react` |
| `VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS` | ReAct 最大轮数 | `5` |
| `VIDEOMAKER_FIXTURE_MODE` | 测试/CI 确定性 LLM 输出 | `false` |
| `VIDEOMAKER_HUMAN_REVIEW_MODE` | generation 人工审批门 | API 默认 `true` |

---

## A. 模块自动化（层级 A）

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd services/composition
python -m pytest -q

cd services/worker
python -m pytest tests/test_hyperframes_material_tool.py `
  tests/test_hyperframes_material_provider.py `
  tests/test_composition_pattern_author.py -q

cd services/api
$env:VIDEOMAKER_FIXTURE_MODE="true"
python -m pytest tests/test_composition_pattern_routes.py `
  tests/test_composition_patterns_list.py `
  tests/test_knowledge_routes.py -q

cd apps/web
npm run test -- CompositionPatternPromotePanel
```

**通过标准：** 上述命令全部 green；无新增 schema / 类型校验失败。

**重点覆盖：**

- composition：sanitize、promote_prepare、path validation、list_candidates、ReAct skill_view 门禁
- worker：HF material provider deposit、composition_pattern_author fixture
- api：GET composition-patterns、POST promote（仅 `confirm`）、generation 归属、错误码、幂等 re-promote
- web：`videoReady` 门禁、loading 文案、已入库 badge

---

## B. HF 管线冒烟（层级 B，无 LLM）

在 `services/composition` 下验证 **build → lint → render**（不经过 Agent）：

```powershell
cd services/composition
$env:PYTHONPATH=".;../shared"
python -m pytest tests/test_composition_engine.py::test_build_composition_template -q
```

或临时脚本调用 `CompositionEngine().render_clip(...)`，使用 `template: composition` + `bodyHtml` / `timelineScript`（GSAP）。

**通过标准：**

- `result.ok == True`
- 输出 MP4 存在且 size > 0
- `composition/index.html` 已生成
- lint-log `ok: true`（未设 `VIDEOMAKER_COMPOSITION_SKIP_LINT`）

---

## C. Skill bootstrap & Agent（层级 C，需 text provider）

### C1. Skill bootstrap

1. 确认 `SkillCatalog` 加载 public + private skills。
2. `author_material_spec` 的 system prompt 含 `<available_skills>` 与 `<skill_usage_rule>`。

### C2. Single-shot Agent

1. `$env:VIDEOMAKER_COMPOSITION_AGENT_MODE="single_shot"`
2. 对 packaging slot（如 `benefit_card`）调用 material author（generation 内 `hyperframes_material` action 或 `CompositionEngine.author_material_spec`）。
3. 返回 JSON 通过 `material-spec` schema；再 `render_clip` 产出 slot MP4。

### C3. ReAct Agent（推荐验证 HF Agent 完整能力）

1. `$env:VIDEOMAKER_COMPOSITION_AGENT_MODE="react"`
2. Workbench text provider 已配置。
3. 同上 slot；观察 agent 调用 `skill_view`、可选 `build_and_lint`，最终 `submit_material_spec`。
4. 验证 `generated/{actionId}/composition/index.html` 与 slot clip MP4。

**通过标准：** lint 通过 + MP4 可播放；Agent run 无 schema 校验失败。

---

## D. Generation 内 HF material（Workbench 局部 E2E）

1. 启动 API + Worker + Web。
2. 已有 project + analyzed sample + brief（可用 fixture 或 live）。
3. 触发 generation，确保至少一个 packaging slot 的 completion 为 `hyperframes_material`。
4. 若 `VIDEOMAKER_HUMAN_REVIEW_MODE=true`，完成 master / storyboard 审批后继续。
5. 检查：

```text
storage/projects/{projectId}/generations/{generationId}/generated/{actionId}/
  composition/index.html
  *.mp4
storage/projects/{projectId}/knowledge/drafts/composition/{generationId}/{slotId}/
  spec.template.json    # deposit 阶段为 instance spec（promote 前）
  lint-log.json
  entry-meta.json       # lintPassed: true
  provenance.json
```

**通过标准：** material completion 成功；draft 自动 deposit；lint 通过。

---

## E. Pattern deposit / promote（方案 C，无 userScore）

Promote **不再**使用 `userScore` 或打分 UI；请求体仅 `{ generationId, slotId, confirm: true }`。

### E1. Workbench UI

1. 全片 generation 完成，Result 区 **成片 MP4** 可见。
2. **CompositionPatternPromotePanel** 展示 draft-only HF 分镜（`GET /api/generations/{generationId}/composition-patterns`）。
3. 点击 **加入知识库**；按钮显示 **正在沉淀动效模式…**（同步等待 ~30–90s）。
4. 成功后该行显示 **已入库** badge。

### E2. API

```http
GET /api/generations/{generation_id}/composition-patterns
POST /api/projects/{project_id}/knowledge/composition/promote
Content-Type: application/json

{ "generationId": "...", "slotId": "...", "confirm": true }
```

### E3. 发布后磁盘

```text
storage/knowledge/{categorySlug}/comp-{generationId}-{slotId}/
  composition-skill.md      # LLM skill
  spec.template.json        # 泛化且 relint 通过
  spec.instance.json        # deposit 原始 instance
  entry-meta.json           # entryKind=composition_pattern
  lint-log.json
  provenance.json
  references/
```

### E4. SQLite

- `knowledge_entries.entry_kind = composition_pattern`
- `structure_json_uri` 指向 `spec.template.json`
- 固定 `entryId = comp-{generationId}-{slotId}`；re-promote 幂等覆盖

### E5. 负向用例

| 场景 | 期望 HTTP / 错误 |
|------|------------------|
| `confirm: false` | 422 |
| `slotId` / `generationId` 含 `../` 或 `/` | 422 `invalid_*` |
| generation 不属于 URL 中 project | 422 `generation_project_mismatch` |
| 无 draft | 422 `draft_not_found` |
| 泛化 relint 失败 | 422 `generalization_lint_failed`（可重试） |
| worker 子进程失败 | 422，message 来自 `finalEvent.error.message` |

### E6. Promote 模块测试（fixture）

```powershell
cd services/composition
python -m pytest tests/test_sanitize.py tests/test_promote_prepare.py tests/test_path_validation.py tests/test_list_candidates.py -q

cd services/worker
python -m pytest tests/test_composition_pattern_author.py -q

cd services/api
$env:VIDEOMAKER_FIXTURE_MODE="true"
python -m pytest tests/test_composition_pattern_routes.py tests/test_composition_patterns_list.py -q

cd apps/web
npm run test -- CompositionPatternPromotePanel
```

---

## F. 全链路 E2E（层级 D，可选）

完整演示路径（竞赛 / 验收用）：

```text
创建 project → 上传/分析 sample → brief + generation plan
→ dual variant generation（含 hyperframes_material slot）
→ 审批（若启用）→ material completion → FFmpeg 成片 MP4
→ Result 区 Promote 面板 → 加入知识库 → storage/knowledge 验证
```

建议与 `docs/demos/p1-demo-checklist.md` 共用 API/Worker/Web 启动步骤；本清单只额外断言 **HF composition** 与 **promote** 相关产物。

---

## Regression

- Legacy templates（`benefit-card`, `ken-burns`）在 `VIDEOMAKER_COMPOSITION_MODE=legacy` 仍可渲染。
- HyperFrames 全片 preview fallback（packaging 文字特效）行为不变。
- Structure knowledge promote（`POST .../samples/{id}/knowledge/promote`）不受 composition promote 影响。
- 路径安全：`validate_storage_segment` 拒绝 traversal ID（见 AGENTS.md § Path segment validation）。
