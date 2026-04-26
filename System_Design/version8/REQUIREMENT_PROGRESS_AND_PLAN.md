# A22 需求达成现状与后续迭代计划

## 1. 先回答当前问题

问题是：

“我们是否已经打通了项目要求的整个系统全链路？剩下的就是往具体功能上优化就行，对吗？”

我的结论是：

- 如果“全链路”指初版工程链路，那么基本已经打通。
- 如果“全链路”指 Requirement 中要求的完整产品能力，那么还没有，不能简单理解成只剩功能微调。

更准确的说法应该是：

- 我们已经完成了 Requirement 的系统骨架搭建与核心主链路联通。
- 但仍有几块 Requirement 里的关键能力没有真正落地，它们不是小优化，而是产品能力补齐。

## 2. Requirement 的核心要求拆解

根据 `/home/siyuen/docker_ws/Requirement/1.png` 到 `5.png`，当前项目真正要交付的不是单纯聊天系统，而是一个：

- 面向情感陪护场景的 AI 虚拟数字人系统
- 具备“感知 -> 认知 -> 干预 -> 再评估”闭环能力
- 具备多模态采集、心理理解、知识支持、数字人表达与陪伴服务能力

可归纳为六类核心需求：

1. 多模态交互与数据采集
2. 心理陪伴对话与知识驱动
3. 多模态融合与状态理解
4. 数字人行为驱动与语音播报
5. 系统指标、稳定性与演示能力
6. 项目材料与可交付性

## 3. 当前已经实现的基础功能

### 3.1 多模态输入基础链路已实现

已实现内容：

- 文本输入
- 浏览器麦克风录音
- 浏览器摄像头预览
- 摄像头 rolling buffer + event window keyframes
- turn 级音视频打包
- `turn_time_window` 统一时序字段

对应代码：

- `local/frontend/src/main.js`
- `local/frontend/src/ui/InputBar.js`
- `local/frontend/src/audio/audioTurnRecorder.js`
- `local/frontend/src/video/cameraTurnRecorder.js`

这部分说明“采集侧底座”已经建立。

### 3.2 远端语音理解基础链路已实现

已实现内容：

- 音频上传到远端
- BELLE Whisper ASR
- 基础语音特征提取
- 音频与转写结果落盘

对应代码：

- `remote/speech-service/services/asr_runtime.py`
- `remote/speech-service/services/feature_extractor.py`

这部分说明“语音模态”已经进入真实推理链路，不再只是前端假文本。

### 3.3 远端视觉理解基础链路已实现

已实现内容：

- 关键帧上传到远端
- Qwen2.5-VL 视觉理解
- 输出结构化视觉特征
- 保存 prompt、raw output、features

对应代码：

- `remote/vision-service/services/frame_feature_extractor.py`
- `remote/vision-service/services/qwen_vl_runtime.py`

这部分说明“视频模态”已经是实际参与推理的辅助模态。

### 3.4 远端 orchestration 主链路已实现

已实现内容：

- 调用 speech-service
- 调用 vision-service
- 进行 multimodal alignment
- 调用 qwen-server
- 生成 `emotion_style`
- 生成 `avatar_action`
- 调用 avatar-service
- 返回统一结构化响应

对应代码：

- `remote/orchestrator/services/dialog_service.py`
- `remote/orchestrator/services/alignment/multimodal_alignment_service.py`
- `remote/orchestrator/adapters/*.py`

这说明系统的“认知中枢”已经有初版实现。

### 3.5 数字人前后端契约已实现

已实现内容：

- `avatar_output` 契约
- viseme / expression / motion cue 结构
- 前端消费这些 cue 做 2D 渲染

对应代码：

- `shared/contracts/schemas.py`
- `remote/avatar-service/routes/generate.py`
- `local/frontend/src/avatar/*`
- `local/frontend/src/ui/AvatarPanel.js`

这说明“数字人输出通路”已经不是空壳。

### 3.6 初版日志与排障基础已实现

已实现内容：

- edge events 日志
- edge bridge 日志
- remote tmp 中间产物落盘

对应代码和产物：

- `local/edge-backend/services/observability.py`
- `shared/observability.py`
- `logs/edge-backend/*`
- `remote/*/services/storage.py`

这说明系统已经有初步可观测性，但还不够全链路。

## 4. 当前与 Requirement 的差距分析

下面这张表里，`已实现` 指主链路已工作，`部分实现` 指骨架已有但能力仍弱，`未实现` 指 Requirement 核心能力尚未真正落地。

| Requirement 目标 | 当前状态 | 现状判断 |
|---|---|---|
| 文本/语音/视频多模态采集 | 已实现 | 初版可用，已能形成 turn 级输入 |
| 多模态统一转发与时序对齐 | 已实现 | `turn_time_window` 和 `alignment_mode` 已建立 |
| 远端语音识别 | 已实现 | 已接 BELLE Whisper |
| 远端视觉特征提取 | 已实现 | 已接 Qwen2.5-VL |
| 10 轮以上上下文对话能力 | 部分实现 | 有 session memory，但仍是轻量内存态，不是完整长期记忆 |
| 基于心理学知识的专业对话 | 部分实现偏弱 | 目前主要是 system prompt + 简单策略，未见真正知识库/RAG |
| 焦虑/抑郁/双向情感障碍风险模型 | 未实现 | 当前没有专门风险评估模型 |
| 视频/语音/文本冲突解决与统一心理理解 | 部分实现 | 当前是结构化拼装和轻规则，不是完整状态建模 |
| TTS 自然播报 | 部分实现 | 代码已留出 CosyVoice 通道，但当前实际运行并未稳定证明已默认打通 |
| 精准口型同步 | 部分实现偏占位 | 前端能吃 viseme，但 viseme 仍是规则生成，不是真正音素级同步 |
| 丰富表情与肢体动作 | 部分实现偏占位 | expression/motion 已有契约，但还是规则输出 |
| 至少 2 个表现丰富的 2D/3D 数字人 | 未实现 | 当前只有单一 `default-2d` scaffold |
| 主动式“评估-引导-干预-再评估”闭环 | 未实现 | 当前是陪伴对话初版，不是完整闭环业务流 |
| WER/SER/时延/数字人指标评测 | 未实现 | 还没有完整 benchmark 和评估脚本 |
| 全链路消息轨迹日志 | 未实现 | 当前有 edge 日志和 remote tmp，但没有统一 `logs/msg` |

## 5. 为什么现在不能说“只剩优化”

因为还有几项 Requirement 里的核心内容，本质上是“能力建设”，不是“体验打磨”。

### 5.1 心理知识与风险评估还没有真正落地

Requirement 明确强调：

- 心理学知识库
- 针对焦虑/抑郁/双向情感障碍风险的 AI 模型
- 专业且有共情力的对话

而当前代码里：

- 没有真正的 RAG/知识库检索链路
- 没有风险分层或状态评估模型
- `policy_service.py` 主要还是关键词和轻规则

这不是小优化，而是核心业务能力缺口。

### 5.2 数字人行为驱动仍是“接口通了”，不是“模型完成了”

当前已经有：

- `viseme_seq`
- `expression_seq`
- `motion_seq`

但生成逻辑仍偏规则化，和 Requirement 里“数字人面部行为驱动模型”还有明显距离。

### 5.3 TTS 与真实音画协同还没有稳定闭环

虽然 `avatar-service` 有 TTS runtime，但从现有 edge bridge 日志看，当前多轮返回的：

- `avatar_output.audio.audio_url: null`
- `reply_audio_url: null`

这意味着“可播放语音 + 与口型联动”的链路还没有成为稳定默认能力。

### 5.4 当前可观测性还不够支撑后续优化

你现在要做的 `logs/msg` 不是附属小功能，而是下一阶段继续做真实优化前非常关键的基础设施。

原因很简单：

- 如果不知道每轮到底哪个服务真的参与了
- 不知道哪个环节降级了
- 不知道融合前后具体输入是什么

后面很多“优化”其实无法有效进行。

## 6. 当前阶段的正确判断

当前项目更准确的阶段定位应当是：

- 已完成“系统骨架 + 主链路联通 + 初版交互 demo”
- 正在进入“补齐 Requirement 关键能力 + 做稳定性与评测”的阶段

所以当前不是：

- 0 到 1 还没开始

也不是：

- 1 到 100 只剩美化

而是：

- 1 到 10 已完成
- 10 到 60 的关键能力还需要继续建设

## 7. 建议的后续开发顺序

下面是我建议的迭代顺序。这个顺序的目标不是“先把所有功能都堆上”，而是先保证后续每次迭代都可观测、可验证、可演示。

### Iteration 1：补齐全链路消息观测

目标：

- 建立 `/home/siyuen/docker_ws/A22/logs/msg`
- 为每个 turn 建立统一 `trace_id`
- 串起 frontend、edge、speech、vision、orchestrator、avatar
- 在 local 侧形成摘要化消息流

这一轮完成后，系统将第一次真正具备“可解释地调优”的能力。

优先事项：

- 前端事件埋点
- edge 统一 trace 生成与透传
- remote 各服务带 trace 记录摘要
- local 聚合 `msg-flow-<run_id>.jsonl/.log`

### Iteration 2：把当前 demo 链路做稳

目标：

- 明确服务是否真实参与，避免静默 fallback
- 提升请求失败时的可诊断性
- 确认 TTS 真实可用并稳定回传音频

优先事项：

- fallback 显式记录
- health/ready 状态细化
- 关键耗时统计
- avatar-service 的 TTS 稳定性验证

### Iteration 3：补齐 Requirement 中最关键的认知能力

目标：

- 把“陪聊系统”升级为“心理陪伴系统”

优先事项：

- 接入心理知识库或 RAG
- 引入结构化风险评估模块
- 形成统一的心理状态对象，而不只是关键词和 tags
- 让 orchestrator 基于状态做更稳定的引导和干预策略

### Iteration 4：补齐数字人表达能力

目标：

- 让数字人真正接近 Requirement 的展示要求

优先事项：

- 至少支持 2 个 avatar 形象
- 让 TTS、viseme、expression、motion 一致对齐
- 提升口型同步真实性
- 丰富表情与动作库
- 视资源决定是否走 2D 增强版还是 3D 路线

### Iteration 5：评测、验收与比赛材料化

目标：

- 让系统从“能跑”变成“能提交、能论证、能演示”

优先事项：

- WER / SER / latency 统计
- 数字人表现评测记录
- 典型场景脚本和 demo case
- 项目方案文档、演示视频、答辩材料

## 8. 一份更务实的阶段性目标表述

如果要用一句适合团队内部对齐的话来概括当前状态，我建议写成：

“当前 A22 已完成初版多模态数字人系统的主架构搭建与核心链路打通，下一阶段重点不是简单功能微调，而是补齐全链路可观测性、心理认知能力、真实数字人表达能力与评测体系，使系统从 MVP 演进为满足 Requirement 的可交付版本。”

## 9. 最终结论

所以，对你原问题的最终回答是：

- 是，初版系统主链路已经通了。
- 但不是，后面不能只理解成“具体功能优化”。

更准确地说，后面要做的是：

1. 先用 `logs/msg` 把系统真正看清楚。
2. 再补齐 Requirement 里还缺的几个关键产品能力。
3. 最后再做体验和指标层面的优化收口。

这会比直接把后续工作理解成“继续堆功能”更稳，也更符合你现在这个项目所处的真实阶段。
