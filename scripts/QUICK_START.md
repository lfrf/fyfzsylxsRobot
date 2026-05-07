# 🚀 快速启动指南

## 📋 前置条件检查

```bash
# 1. 确保在项目目录
cd /home/pi/Desktop/code/fyfzsylxsRobot

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 检查依赖
pip list | grep -E "sherpa-onnx|sounddevice|numpy"
```

---

## 🧪 测试唤醒词（推荐先运行）

```bash
# 运行测试脚本
python scripts/test_wake_word.py

# 预期：看到 "✅ 所有测试通过！唤醒词功能正常"
# 然后说 "你好小星"，应该看到 "🎉 检测到唤醒词！"
```

---

## 🎯 启动完整系统

```bash
# 方式 1: 使用启动脚本（推荐）
bash scripts/start_robot_with_wakeword.sh

# 方式 2: 手动启动（用于调试）
# 先设置环境变量，然后运行：
python -m raspirobot.main live --face-track
```

---

## 📊 工作流程

```
1. 系统启动 → STANDBY (待机，眼睛显示 sleep)
   
2. 说 "你好小星" → WAKE_DETECTED (播放确认音)
   
3. 自动进入 LISTENING (眼睛显示 listening)
   ├─ 启动摄像头
   ├─ 启动人脸识别
   └─ 开始监听语音
   
4. 检测到人脸？
   ├─ 是 → 启动人脸追踪（头部跟随）
   └─ 否 → 继续监听（无追踪）
   
5. 用户说话 → RECORDING → UPLOADING → THINKING → SPEAKING
   
6. 播放完成 → 返回 LISTENING
   
7. 10秒无语音 → 返回 STANDBY (待机)
```

---

## 🔍 实时监控日志

```bash
# 查看最新日志
tail -f /path/to/log/file.jsonl | grep -E "wake_word|state_transition|identity"

# 关键事件：
# - wake_word_detected: 检测到唤醒词
# - state_transition: 状态转换
# - identity_resolved: 识别到人脸
# - face_tracking_enabled_after_identity: 启动人脸追踪
```

---

## 🐛 常见问题

### 问题 1: 唤醒词不响应

```bash
# 检查麦克风设备
python -c "import sounddevice as sd; print(sd.query_devices())"

# 修改设备编号（在启动脚本中）
export ROBOT_WAKE_WORD_DEVICE=0  # 或 1, 2, 3...
```

### 问题 2: 人脸识别不工作

```bash
# 检查视觉服务
curl http://127.0.0.1:29001/v1/video/ingest
curl http://127.0.0.1:29002/v1/vision/identity/from-cache

# 如果服务未运行，先启动远程服务
```

### 问题 3: 人脸追踪不启动

```bash
# 确认启动命令包含 --face-track
# 检查舵机硬件连接
# 查看日志中的 face_tracking 相关错误
```

---

## ⚙️ 配置调整

### 调整唤醒词灵敏度

编辑 `raspirobot/audio/wake_word_sherpa.py`:
```python
keywords_threshold: float = 0.08  # 降低=更灵敏，提高=更严格
```

### 调整工作超时时间

编辑 `scripts/start_robot_with_wakeword.sh`:
```bash
export ROBOT_WORK_IDLE_TIMEOUT_S=15  # 改为15秒
```

### 调整人脸识别频率

编辑 `scripts/start_robot_with_wakeword.sh`:
```bash
export ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S=2.0  # 改为2秒轮询一次
```

---

## 📝 测试清单

启动后依次测试：

- [ ] 说 "你好小星"，系统响应（播放确认音）
- [ ] 进入 LISTENING 状态（眼睛变化）
- [ ] 站在摄像头前，人脸追踪启动（头部跟随）
- [ ] 说话，系统录音并回复
- [ ] 10秒不说话，返回 STANDBY（眼睛变为 sleep）
- [ ] 再次说 "你好小星"，重新唤醒

---

## 🎯 性能优化

### 降低 CPU 占用

```bash
# 减少摄像头分辨率
--face-track-camera-width 240
--face-track-camera-height 180

# 降低人脸识别频率
export ROBOT_IDENTITY_WATCHER_POLL_INTERVAL_S=2.0

# 减少视频上传频率
export ROBOT_VISION_UPLOAD_EVERY=5
```

### 提高响应速度

```bash
# 使用更快的人脸检测器
--face-track-detector haar

# 减少人脸识别上下文时间
export ROBOT_IDENTITY_WATCHER_CONTEXT_SECONDS=1.0
```

---

## 📚 更多文档

- 详细流程: `docs/WAKE_WORD_AND_FACE_DETECTION_FLOW.md`
- 修复总结: `docs/WAKE_WORD_FIX_SUMMARY.md`
- 状态机设计: `docs/STATE_MACHINE.md`

---

## 🆘 获取帮助

如果遇到问题：

1. 运行测试脚本: `python scripts/test_wake_word.py`
2. 检查日志文件中的错误信息
3. 查看 `docs/WAKE_WORD_FIX_SUMMARY.md` 中的故障排查部分
