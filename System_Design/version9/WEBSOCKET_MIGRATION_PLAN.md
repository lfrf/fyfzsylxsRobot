# A22 WebSocket 迁移分步计划（v9）

本文针对当前仓库实现，按“先打通 SSH 通路，再切 WebSocket，再做多模态流对齐”的目标给出可执行步骤。

## 0. 当前基线（已确认）

- 前端 -> local edge-backend：HTTP `/api/chat`
- local edge-backend -> remote orchestrator：HTTP `POST /chat`
- remote orchestrator -> speech/vision/avatar：HTTP
- SSH 仅用于端口转发，不在业务代码中

## 1. 里程碑 M1：打通 edge->orchestrator WebSocket（本轮已落地）

目标：

- 保持现有 HTTP 链路可用
- 新增 WebSocket 通道，允许无缝切换

已改动文件：

- `remote/orchestrator/routes/chat.py`
- `remote/orchestrator/routes/chat_ws.py`
- `remote/orchestrator/app.py`
- `local/edge-backend/config.py`
- `local/edge-backend/services/orchestrator_client.py`
- `local/edge-backend/routes/health.py`
- `local/edge-backend/models.py`
- `local/edge-backend/services/observability.py`
- `local/edge-backend/requirements.txt`
- `compose.local.yaml`
- `shared/contracts/api_v1.md`

使用方式：

1. 启动 remote orchestrator 新代码（含 `/ws/chat`）。
2. local edge 环境变量：
   - `REMOTE_TRANSPORT=auto`（先 WS，失败自动回退 HTTP）
   - `CLOUD_WS_CHAT_ENDPOINT=ws://host.docker.internal:19000/ws/chat`
3. 看 `GET /health` 返回 `remote_transport` 与 `cloud_ws_chat_endpoint`。

## 2. 里程碑 M2：local 侧从“局部处理”改为“全转发”

目标：

- local 不再做视频关键帧抽样和环形策略决策
- local 只做协议封装、转发、日志追踪

建议改动：

1. `local/edge-backend/services/media/video_turn_service.py`
   - 去掉 `select_key_frames(...)` 采样
   - 原样透传 `video_frames` 和 `video_meta`
2. `local/edge-backend/config.py`
   - 废弃或降级 `LOCAL_VIDEO_FRAME_LIMIT`
3. `local/frontend/src/video/cameraTurnRecorder.js`
   - 保留前端采集能力，但减少策略性处理（避免“本地决定关键帧”）

验收标准：

- edge 日志中 `video_frame_count` 与前端采集数一致
- remote 收到的视频帧数量不再被 local 截断

## 3. 里程碑 M3：remote 侧视频环形存储 + 流处理

目标：

- 环形缓冲由 remote 管理
- 允许按窗口执行视频情绪/表情分析

建议新增模块（remote/orchestrator）：

1. `services/stream/video_ring_buffer.py`
   - 按 `session_id/stream_id` 存最近 N 秒帧
2. `routes/stream_ws.py`
   - 新增 `/ws/stream`，接收 video/audio chunk
3. `services/stream/video_aggregator.py`
   - 按 turn window 组包，给 `vision-service`

同步改动（remote/vision-service）：

- 扩展 `ExtractRequest`，支持窗口级输入元数据（window_id、chunk range、stream_id）。

验收标准：

- remote 能在无 local 抽帧前提下稳定提取 `vision_features`
- 能输出窗口级处理耗时、帧数、抽取结果

## 4. 里程碑 M4：voice 流兼容与优化

目标：

- 语音支持 chunk 流 + turn 结束触发识别
- 保留现有 `audio_base64` 兼容路径

建议改动：

1. `remote/speech-service` 增加流式缓存入口（建议先放 orchestrator，再调用 speech-service）
2. turn 结束时统一触发 ASR，输出与当前 `TranscribeResponse` 对齐
3. 失败回退：仍可走一次性 `audio_base64` 路径

验收标准：

- 音频流模式和旧模式在 orchestrator 输出结构一致
- ASR 结果可带 `window_id` 与 `sequence_id`

## 5. 里程碑 M5：多模态对齐输出定义

目标：

- 明确“文本 + 视频 / 语音 + 视频”的统一输出对象

建议新增契约：

- `shared/contracts/schemas.py` 增加 `MultimodalFusionSchema`
  - `fusion_mode`
  - `speech_summary`
  - `vision_summary`
  - `consistency_score`
  - `risk_flags`
  - `decision_trace`

同步修改：

- `remote/orchestrator/services/alignment/*`
- `remote/orchestrator/services/dialog_service.py`

验收标准：

- 每轮响应都有明确融合结果
- 前端状态栏可展示融合模式与关键结论

## 6. 推荐执行顺序（务实）

1. M1（已完成）先让 WS 通道可用并保留 HTTP 回退。
2. M2 取消 local 抽帧截断，先做“完整透传”。
3. M3 在 remote 做视频环形缓存与窗口处理。
4. M4 再做语音流化，保持与旧接口兼容。
5. M5 最后统一多模态输出契约并更新前端展示。

这样做的好处是：每一步都可回退，且不会一次性推翻现有可运行链路。
