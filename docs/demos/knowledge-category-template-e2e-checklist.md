# Knowledge Category Template Bootstrap — E2E Checklist

> **计划：** [2026-06-09-knowledge-category-template-bootstrap-plan.md](../superpowers/plans/2026-06-09-knowledge-category-template-bootstrap-plan.md)  
> **UI 规范：** [2026-06-09-knowledge-template-ui-spec.md](../superpowers/specs/2026-06-09-knowledge-template-ui-spec.md)

## 前置

- [ ] 至少 2–3 条同 `category` 的 published structure knowledge entries（含可 import 源样例）
- [ ] API + Web 本地运行

## 发现

- [ ] 首页 `WorkflowStrip` 下方出现「结构模板库」区块
- [ ] Category 卡片展示真实 poster 或暖色 fallback
- [ ] direct_multimodal 样例 promote 后，首页 category 卡片展示 poster（`samples/{id}/poster.jpg`；无则 backfill）
- [ ] 点击卡片进入 `/templates/{categorySlug}`，标题为 category 中文名而非 slug

## 详情与选用

- [ ] Hero 展示 summary、slotPattern Badge，无 full skill MD
- [ ] Entry 卡片可预览样例、设为主样例、加为参考（最多 2）
- [ ] 主/参考选中态边框区分（primary vs ai）

## 创建项目

- [ ] 「用所选模板创建项目」→ 跳转 `/projects/{id}`
- [ ] 工作台可见 N 条 `analyzed` 样例，sample/knowledge selection 为 user_override
- [ ] 填 brief → generation-plan → 双参考时 structure synthesizer / provenance 可观测

## API 冒烟

```powershell
cd services/api
python -m pytest tests/test_knowledge_category_routes.py tests/test_sample_seed_service.py tests/test_poster_service.py -q
python scripts/backfill_posters.py --dry-run
```
