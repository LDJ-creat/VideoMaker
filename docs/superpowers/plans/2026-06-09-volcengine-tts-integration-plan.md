# 豆包单向流式 TTS 接入计划

## 目标

- 新增 ModelGateway driver **`volcengine_tts`**，调用 [V3 HTTP Chunked 单向流式](https://www.volcengine.com/docs/6561/1598757)（`seed-tts-2.0`）
- 支持 **语速、音量、情感、自然语言语气指令**（`speech_rate` / `loudness_rate` / `emotion` / `context_texts`）
- **参数来源**：工作台全局 `ttsPreferences` + 自动从 `structure.audio.voProfile` 映射；首版不做分镜级 `audioEventRules` 差异
- 保持现有 material 链路：`TTSTool.synthesize()` 仍返回完整 wav bytes → `master.wav` / `{slotId}.wav`

## 模块边界

| 模块 | 文件 | 职责 |
|------|------|------|
| Shared preferences | `services/shared/model_gateway/tts_preferences.py` | 默认 JSON、normalize/patch/validate |
| Shared store | `services/shared/model_gateway/store.py` | `get_tts_preferences` / `update_tts_preferences`；`GET /api/settings/model-gateway` 返回 `ttsPreferences` |
| Worker provider | `services/worker/app/gateway/providers/volcengine_tts.py` | V3 流式合成、PCM→WAV、长文本分句拼接 |
| Factory | `services/worker/app/gateway/providers/tts_factory.py` | `volcengine_tts` vs `openai_compatible` |
| voProfile 映射 | `services/worker/app/pipelines/tts_voice_options.py` | `build_tts_synthesis_options()` |
| Web | `apps/web/features/settings/ModelGatewayStatusPanel.tsx` | TTS driver 下拉 + 豆包精细参数表单 |

## 工作台配置（推荐初始值）

```text
driver:          volcengine_tts
baseUrl:         https://openspeech.bytedance.com/api/v3/tts/unidirectional
apiKey:          {豆包语音控制台 API Key — 非方舟 Ark Key}
model:           (留空或 speaker 镜像)
resourceId:      seed-tts-2.0
speaker:         zh_female_vv_uranus_bigtts
modelVariant:    seed-tts-2.0-expressive
speechRate:      0
contextTexts:    短视频口播，语气自然有起伏，句末适当收束
```

`PUT /api/settings/model-gateway` 可在 `preferences.tts` 中 patch 上述字段（不含 secret）。

## voProfile 映射规则

| voProfile 字段 | 豆包参数 | 规则 |
|----------------|----------|------|
| `pace` slow/medium/fast | `speechRate` | -25 / 0 / +30（可被工作台覆盖） |
| `energy` low/medium/high | `contextTexts` | 追加语气提示 |
| `persona` | `contextTexts` | 前缀：`以{persona}的口吻朗读` |
| `wordsPerMinute` | `speechRate` | 相对 160 WPM 微调（±15 封顶） |
| 工作台 `emotion` | `audio_params.emotion` | 非空时直接使用 |
| 工作台 `contextTexts` | `additions.context_texts[0]` | 与 voProfile 指令拼接（voProfile 在前） |

## E2E 验证步骤

1. 打开工作台 **模型服务 → 配音**，Driver 选 **豆包语音 (Seed TTS 2.0)**，填写 openspeech Base URL 与豆包语音 API Key。
2. 配置 `speaker`、`modelVariant`、`speechRate`、`contextTexts` 等偏好并保存。
3. 跑一条 ≤60s 或长片 generation（需已配置 text + image provider）。
4. 检查 `storage/projects/{projectId}/generations/{generationId}/generated/master.wav`（或 `slot*.wav`）非空。
5. 确认 `generation-plan.json` 含合理 `narrationDurationSec`；播放 `output.mp4` 口播听感与参数一致。

## 验证命令

```powershell
cd services/shared
python -m pytest tests/test_tts_preferences.py -q

cd services/worker
python -m pytest tests/test_volcengine_tts.py tests/test_tts_voice_options.py tests/test_tts_tool.py -q

cd services/api
python -m pytest tests/test_model_gateway_status_route.py -q --basetemp=$env:TEMP\videomaker-pytest

cd apps/web
npm run typecheck
npm run test
```

## Out of scope（首版）

- 双向流式 WebSocket
- 异步长文本任务 API
- 分镜级 `audioEventRules` 语气差异
- 方舟 `ark.cn-beijing.volces.com` 作为 TTS baseUrl
