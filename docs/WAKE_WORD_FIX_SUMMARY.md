# 唤醒词功能修复总结

## 📋 修复内容

本次修复解决了两个问题，并实现了完整的唤醒词 + 人脸检测交互逻辑。

---

## 🔧 修复的问题

### Problem A: 唤醒词初始化失败日志不完整

**文件**: `raspirobot/audio/wake_word_sherpa.py`

**修改内容**:
```python
# 添加了更详细的错误日志
except ImportError:
    logger.error("wake word dependencies missing. Run: pip install sherpa-onnx sounddevice numpy")
    log_event("wake_word_dependencies_missing", level="error")  # 新增
    self._running = False
    return

except Exception as exc:
    logger.error("wake_word_detector_init_failed: %s", exc)
    log_event("wake_word_detector_init_failed", error=str(exc), level="error")  # 新增
    self._running = False
    return
```

**效果**:
- 初始化失败时会记录详细的错误日志
- 帮助快速诊断问题（依赖缺失、模型文件错误等）

---

### Problem B: STANDBY 初始化缺少日志

**文件**: `raspirobot/core/runtime.py`

**修改内容**:
```python
def _ensure_initial_state(self) -> None:
    if self.wake_word_provider is not None:
        if self.state_machine.state == RobotRuntimeState.IDLE:
            # 新增：记录状态转换日志
            log_event(
                "state_transition",
                transition_event="InitialStandby",
                from_state=RobotRuntimeState.IDLE.value,
                to_state=RobotRuntimeState.STANDBY.value,
                mode_id=self.state_machine.mode_id,
            )
            self.state_machine.state = RobotRuntimeState.STANDBY
            self._enter_standby()
            log_event("wake_word_standby_mode_enabled")
```

**效果**:
- 现在可以在日志中看到 IDLE → STANDBY 的转换
- 符合状态机设计规范

---

## 🎯 实现的功能

### 1. 完整的唤醒词 + 人脸检测逻辑

**核心流程**:

```
STANDBY (待机)
   ↓ 用户说"你好小星"
WAKE_DETECTED (检测到唤醒词)
   ↓ 播放确认音
   ↓ 启动 vision_provider
   ↓ 启动 identity_watcher
LISTENING (监听)
   ↓ identity_watcher 持续监控
   ↓ 
   ├─ 检测到人脸 → 启动 face_tracking → 设置 face_id
   └─ 未检测到人脸 → 正常对话（无 face_id）
   ↓
RECORDING → UPLOADING → THINKING → SPEAKING
   ↓
LISTENING (继续监听)
   ↓ 10秒无语音
STANDBY (返回待机)
   ↓ 停止 face_tracking
   ↓ 停止 identity_watcher
   ↓ 清除 face_id
```

---

### 2. 三种人脸检测场景

#### 场景 1: 唤醒时已有人脸
- 唤醒后立即检测到人脸
- 自动启动人脸追踪
- 所有对话请求包含 `face_id`

#### 场景 2: 唤醒时无人脸
- 唤醒后未检测到人脸
- 正常进行对话
- 对话请求不包含 `face_id`

#### 场景 3: 对话中出现人脸
- 开始时无人脸
- 对话过程中检测到人脸
- 动态启动人脸追踪
- 后续请求包含 `face_id`

---

## 📁 新增文件

### 1. 文档

- **`docs/WAKE_WORD_AND_FACE_DETECTION_FLOW.md`**
  - 详细说明唤醒词与人脸检测的交互流程
  - 包含时序图、代码位置、配置参数
  - 测试场景和调试方法

- **`docs/WAKE_WORD_FIX_SUMMARY.md`** (本文件)
  - 修复内容总结
  - 使用指南

### 2. 测试脚本

- **`scripts/test_wake_word.py`**
  - 独立的唤醒词功能测试脚本
  - 检查依赖库、音频设备、模型文件
  - 实时测试唤醒词检测

---

## 🚀 使用指南

### 步骤 1: 确保依赖已安装

```bash
pip install sherpa-onnx sounddevice numpy
```

---

### 步骤 2: 测试唤醒词功能

```bash
cd /home/pi/Desktop/code/fyfzsylxsRobot
source .venv/bin/activate
python scripts/test_wake_word.py
```

**预期输出**:
```
测试 1: 检查依赖库
✅ sherpa_onnx 已安装
✅ sounddevice 已安装
✅ numpy 已安装

测试 2: 检查音频设备
找到 X 个音频设备...

测试 3: 检查模型文件
✅ 模型目录存在
✅ encoder-epoch-13-avg-2-chunk-8-left-64.onnx
✅ decoder-epoch-13-avg-2-chunk-8-left-64.onnx
...

测试 4: 测试唤醒词引擎
✅ 唤醒词引擎创建成功
✅ 唤醒词引擎启动成功

现在请说唤醒词: '你好小星'
按 Ctrl+C 停止测试
```

说"你好小星"后应该看到：
```
🎉 检测到唤醒词！时间: 14:30:25
```

---

### 步骤 3: 启动完整系统

```bash
bash scripts/start_robot_with_wakeword.sh
```

**启动信息**:
```
==========================================
  RobotMatch 机器人启动（完整功能）
==========================================

✅ 唤醒词: 你好星仔 / 你好小星
✅ 唤醒词模型: models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20
✅ 工作超时: 10秒
✅ 远程服务: http://127.0.0.1:29000
✅ 人脸识别: 已启用
✅ 人脸追踪: 已启用

工作流程：
  1. STANDBY (待机) → 说唤醒词 '你好小星'
  2. WAKE_DETECTED → 播放确认音
  3. LISTENING (监听) → 启动人脸识别
  4. 检测到人脸 → 启动人脸追踪
  5. 用户说话 → 处理 → 回复
  6. 10秒无语音 → 返回 STANDBY

人脸检测逻辑：
  • 唤醒时有人 → 直接启动追踪
  • 唤醒时无人 → 正常对话（无追踪）
  • 对话中出现人 → 动态启动追踪
```

---

## 🔍 关键配置参数

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

# 启用身份监控
export ROBOT_IDENTITY_WATCHER_ENABLED=true
export ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S=1.0
export ROBOT_IDENTITY_WATCHER_CONTEXT_SECONDS=2.0
```

---

## 📊 日志监控

### 关键日志事件

启动后，你应该看到以下日志：

1. **初始化阶段**:
```json
{"event": "wake_word_detector_started", "model_dir": "...", "wake_keyword": "你好小星"}
{"event": "wake_word_detection_loop_started", "sample_rate": 16000}
{"event": "state_transition", "transition_event": "InitialStandby", "from_state": "IDLE", "to_state": "STANDBY"}
{"event": "wake_word_standby_mode_enabled"}
```

2. **唤醒阶段**:
```json
{"event": "wake_word_detected", "keyword": "你好小星"}
{"event": "wake_word_triggered"}
{"event": "state_transition", "from_state": "STANDBY", "to_state": "WAKE_DETECTED"}
{"event": "state_transition", "from_state": "WAKE_DETECTED", "to_state": "LISTENING"}
{"event": "identity_watcher_started"}
```

3. **人脸检测阶段**:
```json
{"event": "identity_watcher_poll_started"}
{"event": "identity_resolved", "face_id": "...", "user_id": "..."}
{"event": "face_tracking_enabled_after_identity", "face_id": "..."}
```

4. **返回待机阶段**:
```json
{"event": "work_idle_timeout", "timeout_seconds": 10}
{"event": "state_transition", "from_state": "LISTENING", "to_state": "STANDBY"}
{"event": "face_tracking_stopped"}
{"event": "identity_watcher_stopped"}
```

---

## 🐛 故障排查

### 问题 1: 唤醒词不响应

**检查步骤**:

1. 运行测试脚本：
```bash
python scripts/test_wake_word.py
```

2. 检查日志中是否有错误：
```bash
grep "wake_word" /path/to/log/file.jsonl
```

3. 常见原因：
   - 麦克风设备编号错误 → 修改 `ROBOT_WAKE_WORD_DEVICE`
   - 模型文件缺失 → 检查 `models/` 目录
   - 依赖库未安装 → `pip install sherpa-onnx sounddevice numpy`

---

### 问题 2: 人脸检测不工作

**检查步骤**:

1. 确认视觉服务运行：
```bash
curl http://127.0.0.1:29001/v1/video/ingest
curl http://127.0.0.1:29002/v1/vision/identity/from-cache
```

2. 检查配置：
```bash
echo $ROBOT_VISION_REMOTE_ENABLED
echo $ROBOT_IDENTITY_WATCHER_ENABLED
```

3. 查看日志：
```bash
grep "identity_watcher" /path/to/log/file.jsonl
```

---

### 问题 3: 人脸追踪不启动

**检查步骤**:

1. 确认启动命令包含 `--face-track`：
```bash
python -m raspirobot.main live --face-track
```

2. 检查日志中是否有 `face_tracking_enabled_after_identity` 事件

3. 确认舵机硬件连接正常

---

## 📈 性能优化建议

### 1. 唤醒词检测

- **降低延迟**: 使用 `chunk-8` 模型（已默认）
- **提高准确率**: 调整 `keywords_threshold`（默认 0.08）
- **减少误触发**: 增加 `cooldown_seconds`（默认 2.0 秒）

### 2. 人脸识别

- **降低 CPU 占用**: 增加 `ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S`（默认 1.0 秒）
- **提高响应速度**: 减少 `ROBOT_IDENTITY_WATCHER_CONTEXT_SECONDS`（默认 2.0 秒）
- **减少网络流量**: 增加 `ROBOT_VISION_UPLOAD_EVERY`（默认每 3 帧上传一次）

### 3. 人脸追踪

- **降低 CPU 占用**: 减少摄像头分辨率
  ```bash
  --face-track-camera-width 320
  --face-track-camera-height 240
  ```
- **提高追踪精度**: 使用 MediaPipe 检测器
  ```bash
  --face-track-detector mediapipe
  ```

---

## 🎯 测试清单

在树莓派上测试以下场景：

- [ ] **测试 1**: 运行 `test_wake_word.py`，确认唤醒词检测正常
- [ ] **测试 2**: 启动完整系统，说"你好小星"，确认进入 LISTENING 状态
- [ ] **测试 3**: 唤醒时站在摄像头前，确认人脸追踪启动
- [ ] **测试 4**: 唤醒时不在摄像头前，确认正常对话（无追踪）
- [ ] **测试 5**: 对话中走到摄像头前，确认动态启动追踪
- [ ] **测试 6**: 10 秒不说话，确认返回 STANDBY 状态
- [ ] **测试 7**: 检查日志，确认所有状态转换都有记录

---

## 📚 相关文档

- [唤醒词与人脸检测交互流程](./WAKE_WORD_AND_FACE_DETECTION_FLOW.md)
- [状态机设计](./STATE_MACHINE.md)
- [人脸识别与状态流程](./FACE_RECOGNITION_STATE_FLOW.md)
- [状态转换审计报告](./STATE_TRANSITION_AUDIT.md)
- [用户档案与人脸身份](./USER_PROFILE_AND_FACE_IDENTITY.md)

---

## 🎉 总结

本次修复完成了：

1. ✅ 修复了唤醒词初始化失败的日志记录
2. ✅ 修复了 STANDBY 状态初始化的日志缺失
3. ✅ 实现了完整的唤醒词 + 人脸检测交互逻辑
4. ✅ 支持三种人脸检测场景（唤醒时有人、无人、对话中出现人）
5. ✅ 创建了测试脚本和详细文档

现在系统可以：
- 在待机状态等待唤醒词
- 唤醒后自动启动人脸识别
- 检测到人脸后启动追踪
- 10 秒无语音后返回待机
- 所有状态转换都有完整的日志记录

**下一步**: 在树莓派上测试完整功能！
