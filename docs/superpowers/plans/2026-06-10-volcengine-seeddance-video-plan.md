# 火山方舟 SeedDance 2.0 视频生成接入计划

## 目标

- 新增 ModelGateway video driver **`volcengine_seeddance`**，调用 [火山方舟视频生成 API](https://www.volcengine.com/docs/82379/1520757)
- 与 **`dashscope_wan`** 并列为一等公民；首版支持 **t2v + i2v**（弱匹配素材图 animate）
- 工作台「模型服务 → 生视频」提供 Driver 下拉配置

## 模块边界

| 模块 | 文件 | 职责 |
|------|------|------|
| Driver 解析 | `services/shared/model_gateway/video_driver.py` | Ark host 自动升级、`normalize_video_model`、duration/ratio/resolution 映射 |
| Worker provider | `services/worker/app/gateway/providers/volcengine_seeddance_video.py` | `POST/GET .../contents/generations/tasks`、下载 `video_url` |
| 注册 | `services/worker/app/gateway/providers/pluggable_video.py` | `create_video_provider` 三分支 |
| 画幅透传 | `services/worker/app/providers/video_generation_provider.py` | `aspectRatio: ctx.aspect_ratio` |
| Web | `apps/web/features/settings/ModelGatewayStatusPanel.tsx` | video Driver 下拉 + Ark 默认 URL/模型 |

## 官方 API 摘要

```text
Base URL:  https://ark.cn-beijing.volces.com/api/v3
Submit:    POST /contents/generations/tasks
Poll:      GET  /contents/generations/tasks/{task_id}
Auth:      Authorization: Bearer {方舟 API Key}
Models:    doubao-seedance-2-0-260128（标准）
           doubao-seedance-2-0-fast-260128（快速）
Status:    queued → running → succeeded | failed | expired | cancelled
Result:    content.video_url（24h 内下载）
```

## 工作台配置（推荐）

```text
provider: video
driver:   volcengine_seeddance
baseUrl:  https://ark.cn-beijing.volces.com/api/v3
model:    doubao-seedance-2-0-260128
apiKey:   {方舟 API Key — 非豆包语音 Key}
```

当 `baseUrl` 含 `volces.com` 且 driver 为 `generic_job` 时，store 自动归一化为 `volcengine_seeddance`。

环境变量可选覆盖：`VIDEO_DRIVER=volcengine_seeddance`。

## E2E 验证

1. 模型服务 → 内容生成 → **生视频** → Driver 选「火山方舟 SeedDance 2.0」，保存方舟 Key
2. 配置 text/vision/tts 等必需项，触发含弱视觉 slot 的 generation
3. 观察 `generating_video` 进度；确认 `storage/.../generations/{id}/generated/{slotId}.mp4` 非空
4. 弱匹配为图片的 slot 应走 i2v（`ratio=adaptive` + `image_url` data URL）
5. 视频配额与 `VIDEOMAKER_VIDEO_GEN_FALLBACK` 行为与 Wan 一致

## 验证命令

```powershell
cd services/shared
python -m pytest tests/test_video_driver.py tests/test_model_gateway_store.py -q

cd services/worker
python -m pytest tests/test_volcengine_seeddance_video.py tests/test_dashscope_video.py -q
python -m compileall app

cd apps/web
npm run typecheck
npm run test -- model-gateway-status
```

## Out of scope（首版）

- 多模态参考（video_url/audio_url）、首尾帧、`generate_audio`
- Seedream 生图
- 生视频 connectivity probe
