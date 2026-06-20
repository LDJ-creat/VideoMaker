# ACP Session 内 Lint + 薄 CLI 落地方案

**Status:** implemented  
**Parent:** [`2026-06-19-composition-acp-author-plan.md`](2026-06-19-composition-acp-author-plan.md)  
**E2E checklist:** [`docs/demos/composition-acp-author-e2e-checklist.md`](../demos/composition-acp-author-e2e-checklist.md)

## Goal

- 抽取统一 `lint_pipeline`（MCP / CLI / worker 共用）
- 新增 `python -m composition.cli lint-spec` 供 Cursor/Codex 终端一条命令 build+lint
- Session 内 agent 迭代 lint；worker 保留后置权威门禁
- **在不降质量前提下加速 lint**：分层预检、spec hash 去重、render 复用 lint-draft

## Env（新增）

| Env | Default | Notes |
|-----|---------|-------|
| `VIDEOMAKER_COMPOSITION_LINT_CACHE` | `true` | spec hash 命中时跳过后置 HF lint；render 复用 lint-draft |
| `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX` | `1` | 后置 lint 失败后 ACP repair 轮次 |
| `VIDEOMAKER_MCP_WRITE_SKIP_LINT` | `true`（ACP） | write_material_spec 不在 MCP 内跑 HF |

## Architecture

```text
Session 内:
  lint-spec --schema-only（快速）→ 完整 lint（MCP 或 CLI）→ write_material_spec
  成功 → 写 {scratch}/lint-draft/.lint-passed.json（specHash）

Worker:
  validate（始终）→ hash 命中则跳过后置 HF → render_clip 可复用 lint-draft
  失败 → repair ACP（最多 LINT_REPAIR_MAX 次）
```

## Lint 内容（完整路径）

1. `material-spec` schema
2. `forbidden_copy_guard`
3. `build_composition`（HTML/registry/assets）
4. `hyperframes lint`（repo `node_modules/.bin/hyperframes`）

`--schema-only` 仅跑 1–2 + composition 模板的 `html_safety`，不 build、不跑 HF。

## Lint 加速（v1，不降质量）

| 措施 | 说明 |
|------|------|
| 分层预检 | CLI/MCP `--schema-only`，session 前期秒级反馈 |
| 统一 draft 目录 | `{scratch}/lint-draft/` |
| specContentHash | session lint 通过后 worker 跳过后置 HF |
| render 复用 | `render_clip` hash 命中时不 rebuild |
| CLI 代替 MCP | 同 pipeline，避 Codex 120s MCP 超时 |
| repo HF 锁定 | `resolve_hyperframes_argv`，禁止裸 npx |

**不做：** prompt 规则替代 HF lint；去掉后置门禁；agent 直接 render MP4。

**Deferred v2+：** HF lint 守护进程；registry 增量 install。

## Modules

| Path | Purpose |
|------|---------|
| `services/composition/composition/lint_pipeline.py` | 共享 build+lint + hash cache |
| `services/composition/composition/cli/__main__.py` | `lint-spec` CLI |
| `services/composition/composition/mcp/handlers.py` | 重构调用 lint_pipeline |
| `services/composition/composition/api.py` | render_clip 复用 lint-draft |
| `services/worker/app/composition/acp/author.py` | prompt、后置 hash、repair |
| `services/worker/app/composition/acp/terminal_bridge.py` | 允许 python lint-spec |
| `scripts/lint-material-spec.ps1` | Windows 便利包装（可选） |

## Tests

- `services/composition/tests/test_lint_pipeline.py`
- `services/composition/tests/test_cli_lint_spec.py`
- `services/worker/tests/test_acp_author.py`（repair + cache）
- `services/worker/tests/test_terminal_bridge.py`

## Implementation order

1. lint_pipeline + handlers 重构 + tests
2. CLI lint-spec + tests + ps1
3. hash skip（author 后置 + render_clip 复用）+ tests
4. terminal allowlist + prompt + repair
5. docs + E2E checklist
