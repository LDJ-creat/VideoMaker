# LLM 脚本 → TTS 语气/语速参数（Global 最终版）

**Status:** implemented on `main`  
**E2E:** `docs/demos/narration-alignment-e2e-checklist.md` § VO directive → TTS

## 背景

产品已统一 **global TTS**：单一 `generated/master.wav` + timeline 单条 `vo-master` clip。本方案让 `storyboard_writer` 产出 `narrationVoProfile` 与分镜 `voDirective`，经四层 merge 传入豆包 TTS；分镜参数不同时按 storyboard 顺序分段合成并拼接 PCM。

**不考虑 per_scene**；遗留 `VIDEOMAKER_TTS_MODE=per_scene` 与 contract enum 已冻结/移除。

## 数据流

```text
storyboard_writer
  → script-draft.json (narrationVoProfile + storyboard[].voDirective)
  → generation-plan.json (approve / automated path)
  → TTSProvider → build_tts_synthesis_options → synthesize_master_wav
  → volcengine_tts → master.wav
```

## Contract

- `packages/contracts/schemas/vo-directive.schema.json` — `VoDirective`
- 扩展 `script-draft.schema.json` / `generation-plan.schema.json` / `types.ts`
- `ttsMode` enum 仅 `"global"`

## 参数合并（低 → 高）

1. 工作台 `ttsPreferences`
2. 样本 `structure.audio.voProfile`
3. `plan.narrationVoProfile`
4. `scene.voDirective`

实现：`services/worker/app/pipelines/tts_voice_options.py` — `normalize_vo_directive`, `build_tts_synthesis_options`, `canonical_tts_options_key`

## Global 合成

`services/worker/app/pipelines/tts_synthesis.py`:

- **快路径**：各镜 effective options canonical 相等 → 单次合成整段 `masterNarration`
- **分段路径**：options 不同 → 按分镜 `script` 逐段 TTS，WAV 拼接为 `master.wav`

`TTSProvider` 仅保留 `slotId == __master__` 分支。

## LLM 产出

- Prompt: `packages/prompts/agents/storyboard_writer.md`
- Agent: `services/worker/app/agents/storyboard_writer.py` — 白名单 `voDirective` / `narrationVoProfile`
- 持久化: `assemble_generation_plan`, `script_draft_revise`, `run_planning_from_script_draft`, `run_planning_completion`

## per_scene 清理

- `tts_mode.py` — `resolve_tts_mode` 恒 `global`
- `build_narration_actions` — 单条 `action-master-tts`
- `completion_registry` — TTS voiceover 仅写 `vo-master`
- 相关测试与文档已更新

## Driver 降级

`openai_compatible` TTS 忽略 directive 专有字段；material 阶段 emit `tts_directive_ignored`（一次 per generation）。

## 验证

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd services/worker
python -m pytest tests/test_tts_voice_options.py tests/test_tts_synthesis.py tests/test_storyboard_writer.py tests/test_generation_plan.py tests/test_tts_provider.py -q

cd services/api
python -m pytest tests/test_script_draft_routes.py -q
```

## Out of scope

- NL 改片只重合成 master 某一段
- `audioEventRules` 确定性预填
- openai_compatible 语气参数
- 段间 crossfade
