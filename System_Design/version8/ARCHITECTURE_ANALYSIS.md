# A22 初版产品架构分析

## 1. 文档目的

本文用于描述 `/home/siyuen/docker_ws/A22` 当前已经落地的初版产品架构，回答两个问题：

1. 当前系统到底已经搭起了什么。
2. 这个版本到底是“全链路初版”，还是“接近需求终版”。

结论先说在前面：

- 从工程链路角度看，当前版本已经形成了可运行的初版全链路。
- 从比赛需求达成角度看，当前版本还不是“只剩细节优化”，而是“主链路已通，关键能力仍待补齐”。

## 2. 当前架构的核心定位

当前 A22 更准确的定位是：

- 一个已经打通前端、边缘侧、远端多服务协同的多模态数字人 MVP
- 而不是一个已经完整满足 Requirement 里所有业务目标和评价指标的正式产品

它已经具备了“先跑通系统”的正确骨架：

- 前端负责采集和展示
- 本地 edge-backend 负责会话、打包、归一化、转发
- 远端负责语音、视觉、LLM、数字人输出
- 前端消费 `avatar_output` 做最终渲染

这个方向和 Requirement 里“本地轻、远端重、数字人前端渲染、多模态远端理解”的路线是对齐的。

## 3. 当前系统分层

### 3.1 前端层

代码入口主要在：

- `local/frontend/src/main.js`
- `local/frontend/src/ui/InputBar.js`
- `local/frontend/src/audio/audioTurnRecorder.js`
- `local/frontend/src/video/cameraTurnRecorder.js`
- `local/frontend/src/avatar/renderer.js`

前端当前承担的职责：

- 文本输入
- 麦克风录音
- 浏览器侧语音 hint 识别
- 摄像头预览
- 基于 rolling buffer 的事件窗关键帧采样
- 将 turn 组织成统一请求
- 渲染远端返回的 `avatar_output`
- 播放远端返回的音频 data URL

这说明前端已经不是单纯静态页面，而是一个具备 turn 级多模态采集与数字人播放能力的交互端。

### 3.2 本地边缘层

代码入口主要在：

- `local/edge-backend/routes/chat.py`
- `local/edge-backend/services/input_preprocessor.py`
- `local/edge-backend/services/orchestrator_client.py`
- `local/edge-backend/services/media/*`
- `local/edge-backend/services/observability.py`

edge-backend 当前职责非常明确：

- 维护 `session_id / turn_id`
- 校验一个 turn 只能以 text 或 audio 为主输入
- 把前端音频、视频关键帧、`turn_time_window` 归一化
- 形成远端统一契约请求
- 通过 HTTP 调用远端 orchestrator
- 记录本地事件日志和 bridge 日志

因此它已经从“本地 mock API”升级成了真正的边缘网关。

### 3.3 远端服务层

远端当前已经拆成五个明确服务：

- `remote/qwen-server`
- `remote/orchestrator`
- `remote/speech-service`
- `remote/vision-service`
- `remote/avatar-service`

各自职责如下：

- `speech-service`：BELLE Whisper ASR + 基础语音特征提取
- `vision-service`：Qwen2.5-VL 关键帧理解与结构化视觉特征输出
- `orchestrator`：多模态对齐、上下文拼接、LLM 调用、策略选择、数字人调用
- `avatar-service`：TTS、viseme、表情、动作序列生成
- `qwen-server`：远端 vLLM 推理入口

这说明系统已经不再是单体 demo，而是一个明确的服务化架构。

## 4. 当前初版的真实全链路

结合代码和现有日志，当前已经能跑通下面这条链路：

1. 前端创建 turn，支持 text / audio，视频作为辅助模态。
2. 摄像头开启时，浏览器本地持续维护 frame buffer，并在发送时裁出 event window keyframes。
3. edge-backend 接收请求，归一化 `user_text / audio / video / turn_time_window / alignment_mode`。
4. edge-backend 经 SSH 隧道入口调用远端 orchestrator。
5. orchestrator 对音频调用 `speech-service`，拿到转写和语音特征。
6. orchestrator 对关键帧调用 `vision-service`，拿到视觉特征。
7. orchestrator 做 multimodal alignment，把 transcript、speech cues、vision cues 拼成 LLM 输入。
8. orchestrator 调用远端 qwen-server，生成文本回复。
9. orchestrator 根据策略层给出 `emotion_style` 和 `avatar_action`。
10. orchestrator 调用 `avatar-service` 生成 `avatar_output`。
11. edge-backend 收到结构化响应，返回前端。
12. 前端用 `avatar_output` 驱动 2D 数字人表情、动作、口型，并尝试播放音频。

这一链路已经在现有日志中得到验证。比如：

- `logs/edge-backend/edge-backend-events-edge-backend-20260329T210638-CN08-df408145.log`
- `logs/edge-backend/edge-backend-bridge-edge-backend-20260329T210638-CN08-df408145.log`

这些日志已经出现了：

- `audio_only`
- `video_audio`
- `video_text`
- `response_source: qwen_vllm`
- 返回的 `avatar_output`

所以从“系统能不能跑通”这个问题上，答案是能。

## 5. 当前架构已经打通的内容

### 5.1 多模态 turn 机制已经成立

当前系统已经不是单纯文本聊天，而是明确具备：

- 文本 turn
- 音频 turn
- 文本 + 视频辅助
- 音频 + 视频辅助

并且这些模式已经统一到：

- `session_id`
- `turn_id`
- `turn_time_window`
- `alignment_mode`

这对后续增强是很好的底座。

### 5.2 前后端关于数字人输出的契约已经建立

`shared/contracts/schemas.py` 中已经冻结了：

- `avatar_output`
- `viseme_seq`
- `expression_seq`
- `motion_seq`

这意味着“远端生成驱动信号、前端负责渲染”这条架构决策已经稳定。

### 5.3 远端服务拆分方向已经正确

当前不是把所有逻辑塞进 orchestrator，而是已经拆分出：

- speech
- vision
- llm
- avatar

这使得后续替换模型、做性能优化、加日志与评测都更容易。

### 5.4 远端中间产物落盘机制已经形成

当前远端已经把中间结果写到 `/data/zifeng/siyuan/A22/tmp/...`：

- speech 输入音频和 transcription
- vision prompt / raw output / features
- avatar output / reply wav / runtime error

这对排障和后续回放分析很有价值。

## 6. 当前架构的关键特点

### 6.1 传输方式是 turn-based HTTP，而不是实时流

当前系统采用：

- 浏览器分 turn 采集
- 本地 HTTP 上传
- SSH 隧道转远端
- 远端按 turn 推理

这非常适合当前阶段的工程现实，也符合原型验证优先级。但它不是最终实时系统。

### 6.2 当前多模态融合是“结构化对齐初版”，不是“强认知融合终版”

当前融合逻辑主要在：

- `remote/orchestrator/services/alignment/multimodal_alignment_service.py`

它已经完成了：

- speech context 提取
- vision context 提取
- alignment mode 解析
- LLM user text 组装

但本质上还是“结构化拼装 + 规则化融合”，还不是 Requirement 里强调的深层心理状态统一建模。

### 6.3 当前数字人行为输出是“可消费契约”，不是“行为模型成品”

`avatar-service` 已经能输出：

- `viseme_seq`
- `expression_seq`
- `motion_seq`

但实现上仍偏规则生成：

- `viseme_generator.py`
- `expression_generator.py`
- `motion_generator.py`

这更像是接口已经定了、消费链路已通，但真实行为模型还没完全接上。

## 7. 当前 observability 与 logs/msg 的位置

### 7.1 现在已经有的日志能力

当前已经有两类本地日志：

- `edge-backend-events-*.jsonl/.log`
- `edge-backend-bridge-*.jsonl/.log`

远端还有按 turn 落盘的中间产物：

- speech tmp
- vision tmp
- avatar tmp

所以当前系统并不是“没有日志”，而是“日志已经存在，但还没统一成全链路消息视图”。

### 7.2 当前日志的主要问题

离你希望的 `logs/msg` 还差几个关键点：

- 没有统一 `trace_id`
- 前端事件没有落到统一消息流
- edge、speech、vision、orchestrator、avatar 没有同一条 turn timeline
- 当前 fallback 是否发生不够显式
- 很难一眼看出“本轮到底用了哪些真实模态，哪些走了降级”

### 7.3 `logs/msg` 在当前架构中的正确定位

你的方案是合理的，应该把它定义为：

- `logs/msg` 负责“摘要化全链路消息轨迹”
- `/data/.../tmp` 继续保留远端详细中间产物

也就是说：

- `logs/msg` 是跨 frontend/local/remote 的诊断视图
- `tmp/...` 是各服务自己的深度产物视图

这是一个非常清晰、也很适合当前架构阶段的分工。

## 8. 当前架构的主要限制

当前架构虽然已经成型，但仍存在明显的初版特征：

- 当前只有一个简单 2D avatar scaffold，没有至少 2 个可切换数字人形象
- TTS 虽然有 CosyVoice 接口，但当前实际日志里 `audio_url` 仍多次为空，说明真实语音播报尚未稳定成为默认链路
- 口型、表情、动作序列还是规则生成，不是成熟的人脸行为驱动模型
- 心理知识库 / RAG / 风险评估模型尚未接入
- 多模态冲突解决仍偏轻量规则，不是稳定心理状态建模
- session memory 还是内存态，不是持久化用户画像
- 当前没有完整评测体系，也没有自动化测试体系
- 当前 logs 仍按服务分散，没有统一 `logs/msg`

## 9. 总体判断

当前 A22 的最佳描述不是“功能散乱的半成品”，而是：

- 一个已经拥有正确系统边界和主调用链的初版多模态数字人系统

但它也绝不是：

- 一个只需要继续做一点 UI/Prompt 微调就可以宣称需求完成的系统

更准确的判断是：

- 架构主干已经对了
- 初版全链路已经通了
- 现在进入的是“从 MVP 向 Requirement 完整产品补关键能力”的阶段

因此，后续开发不应只理解成“功能优化”，而应理解成两部分并行：

1. 把 `logs/msg`、可观测性、降级显式化做好，确保我们知道系统每一轮到底发生了什么。
2. 把 Requirement 中尚未真正完成的核心能力补上，尤其是心理知识、风险评估、真实数字人行为驱动与 TTS/Lip-sync。
