# Narration Timing Authority E2E Checklist

验证 canonical TTS 权威 timing + drift 响应 + fix-script 路径。

## 前置

- API + Worker + Web 已启动；Model Gateway TTS 可用（或 fixture 模式）
- 项目含已分析样本 + brief + 至少 4–6 镜 structure

## 1. Canonical 管线

- [ ] 批准 master → 分镜草稿使用 **结构估算** 窗口（无 preview TTS 阶段事件）
- [ ] 批准 storyboard 后任务出现 `synthesizing_canonical_narration` → `adapting_narration_density`
- [ ] `generations/{id}/narration-timing.json` 存在，`role=canonical`
- [ ] `generations/{id}/narration/canonical.wav` 可播放
- [ ] `script-draft.json` 含 `narrationDurationSec`、`narrationTimingStatus=canonical`

## 2. Drift 报告

- [ ] `GET /api/generations/{id}/narration-drift` 返回 slots 数组
- [ ] 工作台 Script Review / NarrationDriftPanel 展示预估 vs 实测
- [ ] 强 drift HF 镜：`compositionAuthorBrief.timingContext` 已写入

## 3. Visual adapt（路径 A）

- [ ] 某镜 drift >30%、字/秒正常：resolutionPath=`visual_adapt`
- [ ] 启用 `VIDEOMAKER_DRIFT_LLM_VISUAL=true` 时生成 `narration/drift-adaptations/` 记录

## 4. Fix-script（路径 B）

- [ ] 字/秒越界镜显示「修正本镜文案并重合成口播」
- [ ] `POST .../narration-slots/{slotId}/fix-script` 成功 → canonical 重合成 → drift 重算
- [ ] Assembly 阶段复用 canonical `master.wav`（无 silent re-TTS）

## 5. Revise 失效

- [ ] Gate 内 NL 改 master/storyboard 后 `narrationTimingStatus=stale`
- [ ] Resume 重跑 canonical → drift → planning

## 6. 回归命令

```powershell
cd services/worker
python -m pytest tests/test_narration_drift.py tests/test_scene_adaptors.py tests/test_composition_validator.py tests/test_canonical_tts_reuse.py -q

cd packages/contracts
npm run check
npm run validate:schemas

cd apps/web
npm run typecheck
```
