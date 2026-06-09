---
name: videomaker-composition
description: VideoMaker MaterialSpec 交卷约束、composition shell、沙箱与 lint 前置要求。
---

# VideoMaker Composition Skill

## When to use

- 任何 `material_author` / HyperFrames 槽位包装任务
- 输出 `template=composition` 的 MaterialSpec
- 提交前必须 `composition_lint_draft`

## MaterialSpec 交卷契约

输出 JSON 必须符合 `material-spec` schema：

```json
{
  "template": "composition",
  "durationSec": 3,
  "composition": {
    "bodyHtml": "<div id=\"root\">...</div>",
    "styles": ".card { opacity: 0; }",
    "timelineScript": "tl.set('#root', { autoAlpha: 1 }, 0);",
    "registryBlocks": ["caption-style-minimal"]
  }
}
```

## 禁止项

- 禁止输出完整 `<!doctype html>` 或 `<html>` 文档 — shell 由 builder 注入
- 禁止 `javascript:` URL、`eval`、`fetch` 到外部域
- `bodyHtml` 仅允许槽位片段（`#root` 或 composition 容器内 markup）
- 不要内联 `<script src=...>` 加载外部库 — 使用 shell 已提供的 GSAP / HyperFrames 适配器

## 环境约束

- 画布尺寸由 `aspectRatio` 决定（默认 9:16）

## Finish 润色（`finishBrief` + video 底片）

当 payload 含 `finishBrief.completionMode=source_then_polish` 且 `assetRefs` 含 **video**：

- 底片 `<video>` 必须保持可见，占主视觉层；overlay 在上层
- 禁止全屏色块或新视频替换底片内容
- 字幕/角标/花字遵循 safe area，不遮挡主体
- 静图底片可用 ken-burns 式 scale/pan + overlay
- 资产引用走 `params.assetRefs`，URI 相对 `asset_root`
- `registryBlocks` 须来自 `registry_list` 或已安装 catalog
- 提交前：先 `skill_view` 相关 HF skills，再 `composition_lint_draft`，最后 `submit_material_spec`

## Legacy 模板

若无法产出安全 composition，可回退 legacy 模板（`benefit-card` / `title-lower-third` / `ken-burns`），但仍须通过 schema 校验。
