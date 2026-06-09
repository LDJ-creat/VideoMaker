# Pexels 素材库 E2E 验收清单

## 前置

1. 在 [pexels.com/api](https://www.pexels.com/api/) 申请免费 API Key
2. 启动 API + Worker + Web
3. 打开 **设置 → Pexels 素材库**，保存 Key 并「测试连接」成功

## 场景 1 — usage_scene 走 Pexels

1. 创建项目，Brief 主题为泛化 lifestyle（不含具体 SKU 特写需求）
2. 不上传 usage 场景视频，仅保留文本 Brief
3. 完成样例分析与生成（`high_conversion` 变体优先 stock）
4. 在缺口报告 / 分镜卡片确认至少一个槽位 provider 为 **Pexels 素材**
5. 预览 timeline：对应 clip 可播放；tooltip 含摄影师名与 Pexels 链接

## 场景 2 — product_closeup 禁止 stock

1. Brief 含明确 `productName`，结构含 `product_closeup` 槽位
2. 生成后确认该槽位 **不** 使用 `stock_media_search`，走 AI 生图/生视频或用户素材

## 场景 3 — 未配置 Key 零回归

1. 清空 Pexels Key（或新环境未配置）
2. 重复生成流程，确认仍走原有 AIGC 路径，generation 不 fail-fast

## 场景 4 — Pexels 无结果 fallback

1. 使用极冷门 query 场景（或 mock 空结果）
2. 确认自动 fallback `image_generation` / `video_generation`，任务继续完成

## 场景 5 — stock video + HF finish 润色

1. 配置 Pexels Key；Brief 为 lifestyle / usage_scene
2. 分镜 visual 含「字幕 / lower third / 角标」等包装关键词，或 slot 含 `packagingRequirements`
3. 生成后确认 gap item `completionMode=source_then_polish`，completion actions 含 `action-{slotId}`（stock）+ `action-{slotId}-finish`（hyperframes_material）
4. 预览 MP4：底片为 Pexels B-roll，上层有 HF overlay（字幕条/角标等）

## 场景 6 — hf_native 全合成

1. 结构含 `benefit_card` / `hook_text` 等 packaging role
2. 确认 provider chain 仅 `hyperframes_material`，无 stock / AIGC 主路径

## 场景 7 — AIGC 仅 must-use

1. `product_closeup` + 本品 Brief → 仅 `video_generation` / `image_generation`，无 Pexels
2. 普通 B-roll 槽位在 reconcile 后不应默认使用 `video_generation`（除非 LLM 标注 must-use 且 quota 允许）

## 合规

- 结果面板或分镜 metadata 展示 `stockAttribution`（摄影师 + pageUrl）
