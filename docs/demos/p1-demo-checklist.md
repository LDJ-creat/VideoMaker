# P1 Demo Checklist

详细步骤、环境变量、API 抽检与异常场景见 **[`p1-manual-test-guide.md`](./p1-manual-test-guide.md)**。

P0 底座检查仍适用 — [`p0-demo-checklist.md`](./p0-demo-checklist.md)。

---

## 测试路径

- [ ] **Fixture 冒烟**：`VIDEOMAKER_FIXTURE_MODE=true` — 流程 / UI / SSE / 双变体 / 改片 API（无需外部 Key）
- [ ] **Live 验收**：`VIDEOMAKER_FIXTURE_MODE=false` + ModelGateway env — 完整 P1 演示（最终签字项）

---

## 0. 预检

- [ ] `GET /health` → `{ "ok": true }`
- [ ] `GET /api/settings/model-gateway` 无泄露 Key；Live 下 text/image 已配置（工作台「模型服务」保存或 PUT）
- [ ] 工作台 **ModelGateway 状态** 面板与 API 一致
- [ ] Web `VIDEOMAKER_USE_FIXTURE_FALLBACK=false`（测真实 API）

---

## 1. P0 底座（必做）

- [ ] 创建项目；本地上传样例 → `storage/projects/{projectId}/samples/`
- [ ] **开始样例分析** → SSE/轮询进度；刷新后 task 恢复
- [ ] Brief + 用户素材保存并刷新后仍在

---

## 2. LLM 结构与 Evidence

- [ ] 分析完成 → **样例分析** 面板 metadata / transcript / shots
- [ ] **结构槽** 显示 narrative / rhythm / packaging / slots
- [ ] **结构证据** 区：关键帧 + 字幕 evidence；点击联动 slot 高亮
- [ ] `GET /api/samples/{id}/structure` 含 `evidence[]`
- [ ] LLM 失败时 **无规则 fallback**；UI 显示格式校验错误 + 可重试

---

## 3. 素材理解

- [ ] 生成流程经过 **分析素材** 阶段
- [ ] Asset inventory 含 **visualTags**
- [ ] 含 **suggestedSegmentRoles**（hook / mid / cta 等推荐）

---

## 4. 槽位匹配与缺口

- [ ] StructureSlotBoard 每 slot 有 **matchReason**
- [ ] Gap 面板：matched / weak / missing
- [ ] 弱/缺 slot 显示 **provider**（`hyperframes_material` / `image_generation` / `video_generation` / `tts` / `asset_reuse`）
- [ ] `GeneratedAssetBadge` 正确标注来源

---

## 5. 双变体生成

- [ ] **VariantPicker** 默认 **高点击版 + 高转化版**
- [ ] `POST /api/projects/{id}/generation-plan`  spawn **两个** task（默认全选）
- [ ] **MultiTaskProgressPanel** 并排跟踪两任务
- [ ] P1 中文 stage：运行 AI 分析、AI 生图/生视频/配音、渲染包装片段等
- [ ] **TaskArtifactPreview** 在素材阶段展示增量 artifact
- [ ] **VariantTabs** + **VariantCompareView** 并排对比 storyboard / timeline
- [ ] 刷新后 `GET .../generations/latest` 恢复两变体

---

## 6. AIGC / HyperFrames / TTS

- [ ] 每 `generationId` **最多 1 次** `video_generation`（超额 → `video_quota_exceeded` + UI 提示）
- [ ] 至少 **1 段 AI 生视频** clip（Live）或 fixture artifact
- [ ] 至少 **1 个 HyperFrames** 包装/卖点卡片段
- [ ] HyperFrames **preview.html** 可打开
- [ ] **TTS 配音** 在最终 preview 可听（Live）

---

## 7. 自然语言改片

- [ ] 输入「开头更抓人，字幕少一点」→ **提交改片**
- [ ] 新 generation + 阶段：理解改片指令 / 应用改片
- [ ] **EditIntentList** 展示解析 intent
- [ ] **TimelineDiffSummary** 展示与源版本 diff
- [ ] `POST /api/generations/{id}/revise` 返回 202

---

## 8. Retry / Checkpoint

- [ ] 失败任务 **重试** 使用 **同一 taskId**（`POST .../tasks/{id}/retry`）
- [ ] 从 checkpoint **跳过已完成 stage** 恢复
- [ ] 重试仍走 **LLM Agent 路径**（非 P0 规则 pipeline）

---

## 9. 可观测性

- [ ] **查看 AI 调用链**（AgentRunsDrawer）
- [ ] `GET /api/generations/{id}/agent-runs` 返回 runs 列表

---

## 10. 自动化门禁（合并前）

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd ../../services/api && python -m pytest && python -m compileall app
cd ../worker && python -m pytest && python -m compileall app
cd ../../apps/web && npm run typecheck && npm run test
```

- [ ] 上述命令全部通过
