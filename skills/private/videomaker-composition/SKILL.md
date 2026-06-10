---
name: videomaker-composition
description: VideoMaker MaterialSpec 交卷约束、composition shell、沙箱与 lint 前置要求。
---

# VideoMaker Composition Skill

## When to use

- 任何 `material_author` / HyperFrames 槽位包装任务
- 输出 `template=composition` 的 MaterialSpec
- 提交前必须 `composition_lint_draft`

画面审美与反 AI 指纹见 **`skills/private/videomaker-visual-craft/SKILL.md`**（与本文并列必读）。

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

## timelineScript 规则（HyperFrames shell）

- Shell **已注入** GSAP timeline 变量 `tl` — **禁止**在 `timelineScript` 里写 `const tl`、`let tl` 或 `gsap.timeline()`
- 直接使用 `tl.set(...)` / `tl.from(...)` / `tl.to(...)` 即可
- 若需注册 timeline，可写 `window.__timelines['main'] = tl;`，且 `main` 必须与根节点 `data-composition-id` 一致

## Video 底片规则（lint 必过）

当 `assetRefs` 含 **video** 或 `bodyHtml` 含 `<video>`：

- 每个 `<video>` 必须有 **唯一 `id`**（如 `id="base-video"`）
- 有 `src` 的 `<video>` 必须有 **`data-start="0"`**（或正确入点）
- 若槽位时长短于源片，还需 **`data-duration`** 等于槽位秒数
- 底片 video 占主视觉底层，overlay / 字幕在上层，禁止全屏遮罩替换底片

提交前用 `composition_lint_draft` 验证以上项。

## 禁止项

- 禁止输出完整 `<!doctype html>` 或 `<html>` 文档 — shell 由 builder 注入
- 禁止 `javascript:` URL、`eval`、`fetch` 到外部域
- `bodyHtml` 仅允许槽位片段（`#root` 或 composition 容器内 markup）
- 不要内联 `<script src=...>` 加载外部库 — 使用 shell 已提供的 GSAP / HyperFrames 适配器

## 环境约束与画幅适配

画布由 `renderTarget` / `aspectRatio` 决定。按画幅选择字号与安全区：

| aspectRatio | 画布 | 主标题 | 副标题 | 安全边距 | 构图 |
|-------------|------|--------|--------|----------|------|
| 9:16 | 1080×1920 | 72–96px | 40–52px | 左右 8% / 上下 12% | 竖屏居中，避免过小字 |
| 16:9 | 1920×1080 | 48–64px | 28–36px | 6% | 横屏 lower-third 优先 |
| 1:1 | 1080×1080 | 56–72px | 32–40px | 7% | 方形居中卡片 |

## Slot 时长（`slotTiming`）

- `durationSec` **必须**等于 `slotTiming.durationSec`
- `timelineScript` 动画应铺满整段时长，末帧 hold，禁止动画结束后黑场
- `<video>` 的 `data-duration` 与 `slotTiming.durationSec` 一致

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
