# 唤醒词与人脸检测交互流程

## 📋 概述

本文档详细说明唤醒词触发后，系统如何根据人脸检测结果来决定交互方式。

---

## 🎯 核心需求

1. **唤醒词功能正常**：用户说"你好小星"能够唤醒机器人
2. **人脸检测逻辑**：
   - 唤醒后检测到人 → 直接进行对话交互 + 启动人脸追踪
   - 唤醒后未检测到人 → 进行对话交互（无人脸追踪）
   - 先未检测到后检测到人 → 动态启动人脸追踪

---

## 🔄 完整状态流程

### 场景1: 唤醒时已检测到人脸

```
STANDBY (待机，唤醒词监听中)
   ↓ 用户说"你好小星"
WAKE_DETECTED (检测到唤醒词)
   ↓ 播放确认音
LISTENING (开始监听用户语音)
   ↓ 同时启动 identity_watcher
   ↓ identity_watcher 检测到人脸
   ↓ 调用 handle_identity_resolved()
   ↓ 启动 face_tracking (人脸追踪)
   ↓ 设置 face_id 到 request_options
   ↓ 用户开始说话
RECORDING (录音中)
   ↓ 语音结束
UPLOADING (上传音频)
   ↓ 发送请求（包含 face_id）
THINKING (等待LLM回复)
   ↓ 收到回复
SPEAKING (播放回复)
   ↓ 播放完成
LISTENING (继续监听)
   ↓ 10秒无语音
STANDBY (返回待机)
   ↓ 停止 face_tracking
   ↓ 停止 identity_watcher
   ↓ 清除 face_id
```

---

### 场景2: 唤醒时未检测到人脸

```
STANDBY (待机，唤醒词监听中)
   ↓ 用户说"你好小星"
WAKE_DETECTED (检测到唤醒词)
   ↓ 播放确认音
LISTENING (开始监听用户语音)
   ↓ 同时启动 identity_watcher
   ↓ identity_watcher 未检测到人脸
   ↓ 用户开始说话
RECORDING (录音中)
   ↓ 语音结束
UPLOADING (上传音频)
   ↓ 发送请求（无 face_id）
THINKING (等待LLM回复)
   ↓ 收到回复
SPEAKING (播放回复)
   ↓ 播放完成
LISTENING (继续监听)
   ↓ 10秒无语音
STANDBY (返回待机)
```

---

### 场景3: 先未检测到，后检测到人脸

```
STANDBY (待机)
   ↓ 唤醒
LISTENING (监听中，无人脸)
   ↓ identity_watcher 持续监控
   ↓ 检测到人脸！
   ↓ 调用 handle_identity_resolved()
   ↓ 启动 face_tracking
   ↓ 设置 face_id
   ↓ 后续对话都会包含 face_id
RECORDING → UPLOADING → THINKING → SPEAKING
   ↓ (人脸追踪持续运行)
LISTENING (继续监听，有人脸追踪)
```

---

## 🔧 关键组件

### 1. Wake Word Provider (唤醒词引擎)

**文件**: `raspirobot/audio/wake_word_sherpa.py`

**功能**:
- 后台线程持续监听麦克风
- 检测到"你好小星"后设置 `_triggered = True`
- `poll()` 方法返回 True 并清除标志位

**修复内容**:
- 添加了更详细的错误日志
- 使用 `sounddevice` 直接读取麦克风（不依赖 `sherpa_onnx.Microphone`）

---

### 2. Identity Watcher (身份监控器)

**文件**: `raspirobot/vision/identity_watcher.py`

**功能**:
- 从 `vision_provider` 获取视频帧
- 调用远程 API 进行人脸识别
- 检测到人脸后调用 `on_identity_resolved` 回调

**启动时机**:
- 从 STANDBY → LISTENING 时启动
- 在 `runtime.py:61` 调用 `_start_identity_watcher(shared_camera_mode=False)`

**停止时机**:
- 从 LISTENING → STANDBY 时停止
- 在 `runtime.py:177` 调用 `_stop_identity_watcher()`

---

### 3. Face Tracking Lifecycle (人脸追踪生命周期)

**文件**: `raspirobot/main.py` (FaceTrackingLifecycle 类)

**功能**:
- 管理舵机云台的人脸追踪线程
- 启动后持续追踪检测到的人脸
- 让机器人"头部"跟随人脸移动

**启动时机**:
- `handle_identity_resolved()` 被调用时
- 只有在 LISTENING/RECORDING/UPLOADING/THINKING/SPEAKING 状态时才启动
- STANDBY 状态忽略人脸检测结果

**停止时机**:
- 返回 STANDBY 状态时停止

---

### 4. Runtime Handle Identity Resolved (身份解析处理)

**文件**: `raspirobot/core/runtime.py:186-209`

**功能**:
```python
def handle_identity_resolved(self, face_identity, result) -> None:
    # 1. 提取 face_id
    face_id = str(getattr(result, "face_id", None) or ...)
    
    # 2. 忽略 STANDBY 状态的人脸检测
    if self.state_machine.state == RobotRuntimeState.STANDBY:
        return
    
    # 3. 避免重复处理同一个人脸
    if self._tracking_face_id == face_id:
        return
    
    # 4. 设置 face_id 到请求参数
    self._set_active_face_identity(face_id)
    
    # 5. 切换到共享摄像头模式（人脸追踪会注入帧）
    self._start_vision_provider(shared_camera_mode=True)
    
    # 6. 启动人脸追踪
    if self._start_face_tracking():
        self._tracking_face_id = face_id
        log_event("face_tracking_enabled_after_identity", ...)
```

---

## 📊 时序图

### 唤醒 → 检测到人脸 → 对话

```
用户          Wake Word      Runtime        Identity       Face          Vision
              Provider                      Watcher        Tracking      Provider
 |                |              |              |              |              |
 |--"你好小星"-->  |              |              |              |              |
 |                |--poll()-->   |              |              |              |
 |                |<--True----   |              |              |              |
 |                |              |--STANDBY→LISTENING          |              |
 |                |              |--start_identity_watcher()-->|              |
 |                |              |--start_vision_provider()------------------>|
 |                |              |              |--poll()----->|              |
 |                |              |              |<--context----|              |
 |                |              |              |--resolve_face()             |
 |                |              |<--handle_identity_resolved(face_id)        |
 |                |              |--set_active_face_identity(face_id)         |
 |                |              |--start_face_tracking()----->|              |
 |                |              |              |              |--启动追踪--> |
 |--"今天天气怎么样"------------>  |              |              |              |
 |                |              |--RECORDING   |              |              |
 |                |              |--UPLOADING   |              |              |
 |                |              |--THINKING    |              |              |
 |                |              |  (请求包含face_id)           |              |
 |                |              |--SPEAKING    |              |              |
 |<--"今天天气很好"---------------|              |              |              |
 |                |              |--LISTENING   |              |              |
 |                |              |  (10秒超时)  |              |              |
 |                |              |--STANDBY     |              |              |
 |                |              |--stop_face_tracking()------>|              |
 |                |              |--stop_identity_watcher()--->|              |
 |                |              |--stop_vision_provider()-------------------->|
```

---

## 🔍 关键代码位置

### 1. 唤醒词触发 (runtime.py:57-67)

```python
if self.state_machine.state == RobotRuntimeState.STANDBY:
    self._start_wake_word_provider()
    if self.wake_word_provider is not None and self.wake_word_provider.poll():
        log_event("wake_word_triggered")
        self._stop_wake_word_provider()
        self._start_vision_provider(shared_camera_mode=False)  # 启动视觉
        self._start_identity_watcher(shared_camera_mode=False) # 启动身份监控
        self.state_machine.transition(RobotEvent.WAKE_WORD_DETECTED)
        self.state_machine.transition(RobotEvent.WAKE_ACK_DONE)
        self._set_eyes("listening")
```

**关键点**:
- 唤醒后立即启动 `vision_provider` 和 `identity_watcher`
- 此时还没有检测到人脸，只是开始监控

---

### 2. 身份解析回调 (runtime.py:186-209)

```python
def handle_identity_resolved(self, face_identity, result) -> None:
    face_id = str(getattr(result, "face_id", None) or ...)
    if not face_id:
        return
    if self.state_machine.state == RobotRuntimeState.STANDBY:
        return  # STANDBY 状态忽略人脸检测
    if self._tracking_face_id == face_id:
        return  # 避免重复处理
    
    self._set_active_face_identity(face_id)  # 设置到请求参数
    
    # 切换到共享摄像头模式
    self._start_vision_provider(shared_camera_mode=True)
    
    # 启动人脸追踪
    if self._start_face_tracking():
        self._tracking_face_id = face_id
```

**关键点**:
- 只在非 STANDBY 状态处理人脸检测
- 动态启动人脸追踪
- 设置 `face_id` 后，后续所有请求都会包含这个 ID

---

### 3. 返回待机 (runtime.py:175-182)

```python
def _enter_standby(self) -> None:
    self._clear_active_face_identity()  # 清除 face_id
    self._stop_identity_watcher()       # 停止身份监控
    self._stop_face_tracking()          # 停止人脸追踪
    self._stop_vision_provider()        # 停止视觉提供者
    self._set_eyes("sleep")             # 眼睛进入睡眠状态
    self._start_wake_word_provider()    # 重新启动唤醒词监听
```

**关键点**:
- 清理所有运行中的组件
- 重新启动唤醒词监听

---

## ⚙️ 配置参数

### 唤醒词配置

```bash
# 启用唤醒词
export ROBOT_WAKE_WORD_ENABLED=true

# 模型目录
export ROBOT_WAKE_WORD_MODEL_DIR=models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20

# 关键词文件
export ROBOT_WAKE_WORD_KEYWORDS=models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/keywords.txt

# 麦克风设备（sounddevice 设备编号）
export ROBOT_WAKE_WORD_DEVICE=1

# 工作模式超时（秒）
export ROBOT_WORK_IDLE_TIMEOUT_S=10
```

---

### 视觉和身份识别配置

```bash
# 启用远程视觉服务
export ROBOT_VISION_REMOTE_ENABLED=true

# 视频上传地址
export ROBOT_VISION_INGEST_URL=http://127.0.0.1:29001/v1/video/ingest

# 身份识别地址
export ROBOT_VISION_FROM_CACHE_URL=http://127.0.0.1:29002/v1/vision/identity/from-cache

# 身份监控配置
export ROBOT_IDENTITY_WATCHER_ENABLED=true
export ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S=1.0
export ROBOT_IDENTITY_WATCHER_CONTEXT_SECONDS=2.0
export ROBOT_IDENTITY_RESOLVE_TIMEOUT_S=5.0

# 人脸来源（用于持久化）
export ROBOT_IDENTITY_PERSISTABLE_FACE_SOURCES=insightface
```

---

### 人脸追踪配置

```bash
# 启用人脸追踪（命令行参数）
--face-track

# 舵机配置
--face-track-pan-channel 0
--face-track-tilt-channel 1
--face-track-i2c-address 0x40

# 角度限制
--face-track-pan-min-angle 0.0
--face-track-pan-max-angle 270.0
--face-track-tilt-min-angle 35.0
--face-track-tilt-max-angle 235.0

# 中心位置
--face-track-center-pan 135.0
--face-track-center-tilt 135.0
```

---

## 🐛 调试和日志

### 关键日志事件

1. **唤醒词相关**:
   - `wake_word_detector_started` - 唤醒词引擎启动
   - `wake_word_detection_loop_started` - 检测循环开始
   - `wake_word_detected` - 检测到唤醒词
   - `wake_word_triggered` - 唤醒词触发状态转换

2. **身份识别相关**:
   - `identity_watcher_started` - 身份监控启动
   - `identity_watcher_poll_started` - 开始轮询
   - `identity_resolved` - 身份解析成功
   - `face_tracking_enabled_after_identity` - 启动人脸追踪

3. **状态转换相关**:
   - `state_transition` - 所有状态转换
   - `InitialStandby` - 初始化进入待机
   - `wake_word_standby_mode_enabled` - 待机模式启用

---

## 🎯 测试场景

### 测试1: 唤醒时有人

1. 机器人处于 STANDBY 状态
2. 用户站在摄像头前
3. 用户说"你好小星"
4. **预期结果**:
   - 状态转换: STANDBY → WAKE_DETECTED → LISTENING
   - 启动 identity_watcher
   - 检测到人脸，启动 face_tracking
   - 日志包含 `face_tracking_enabled_after_identity`

---

### 测试2: 唤醒时无人

1. 机器人处于 STANDBY 状态
2. 摄像头前无人
3. 用户在远处说"你好小星"
4. **预期结果**:
   - 状态转换: STANDBY → WAKE_DETECTED → LISTENING
   - 启动 identity_watcher
   - 未检测到人脸，不启动 face_tracking
   - 对话正常进行（无 face_id）

---

### 测试3: 对话中途出现人脸

1. 机器人处于 LISTENING 状态（无人脸）
2. 用户走到摄像头前
3. **预期结果**:
   - identity_watcher 检测到人脸
   - 调用 `handle_identity_resolved()`
   - 启动 face_tracking
   - 后续请求包含 face_id
   - 日志包含 `face_tracking_enabled_after_identity`

---

### 测试4: 超时返回待机

1. 机器人处于 LISTENING 状态（有人脸追踪）
2. 10秒内无语音输入
3. **预期结果**:
   - 状态转换: LISTENING → STANDBY
   - 停止 face_tracking
   - 停止 identity_watcher
   - 清除 face_id
   - 重新启动 wake_word_provider

---

## 📝 实现总结

### ✅ 已实现的功能

1. **唤醒词检测**: 使用 sherpa-onnx 模型检测"你好小星"
2. **状态机完整**: STANDBY ↔ LISTENING 循环
3. **身份监控**: 持续监控视频帧，识别人脸
4. **动态人脸追踪**: 检测到人脸后自动启动追踪
5. **face_id 传递**: 识别到的人脸 ID 会传递给 LLM
6. **超时机制**: 10秒无语音自动返回待机

---

### 🔧 修复的问题

1. **Problem A**: 添加了详细的错误日志，帮助诊断初始化失败
2. **Problem B**: 修复了 STANDBY 初始化的日志记录

---

### 🎯 核心逻辑

**唤醒后的处理流程**:

```python
# 1. 唤醒词触发
wake_word_detected()
  ↓
# 2. 启动视觉和身份监控
start_vision_provider()
start_identity_watcher()
  ↓
# 3. 进入 LISTENING 状态
state = LISTENING
  ↓
# 4. identity_watcher 持续监控
while state == LISTENING:
    context = vision_provider.get_context()
    if has_face(context):
        handle_identity_resolved(face_id)
          ↓
        # 5. 启动人脸追踪
        start_face_tracking()
        set_active_face_identity(face_id)
  ↓
# 6. 用户说话，进入对话流程
# 7. 10秒无语音，返回 STANDBY
# 8. 清理所有组件
```

---

## 🚀 启动命令

```bash
cd /home/pi/Desktop/code/fyfzsylxsRobot
source .venv/bin/activate

# 设置环境变量
export ROBOT_WAKE_WORD_ENABLED=true
export ROBOT_WAKE_WORD_MODEL_DIR=models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20
export ROBOT_WAKE_WORD_KEYWORDS=models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/keywords.txt
export ROBOT_WAKE_WORD_DEVICE=1
export ROBOT_WORK_IDLE_TIMEOUT_S=10

export ROBOT_VISION_REMOTE_ENABLED=true
export ROBOT_VISION_INGEST_URL=http://127.0.0.1:29001/v1/video/ingest
export ROBOT_VISION_FROM_CACHE_URL=http://127.0.0.1:29002/v1/vision/identity/from-cache

export ROBOT_IDENTITY_WATCHER_ENABLED=true
export ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S=1.0

# 启动（带人脸追踪）
python -m raspirobot.main live --face-track \
  --face-track-pan-channel 0 \
  --face-track-tilt-channel 1 \
  --face-track-i2c-address 0x40 \
  --face-track-center-pan 135.0 \
  --face-track-center-tilt 135.0 \
  --face-track-pan-min-angle 0.0 \
  --face-track-pan-max-angle 270.0 \
  --face-track-tilt-min-angle 35.0 \
  --face-track-tilt-max-angle 235.0
```

---

## 📚 相关文档

- [状态机设计](./STATE_MACHINE.md)
- [人脸识别与状态流程](./FACE_RECOGNITION_STATE_FLOW.md)
- [用户档案与人脸身份](./USER_PROFILE_AND_FACE_IDENTITY.md)
- [状态转换审计报告](./STATE_TRANSITION_AUDIT.md)
