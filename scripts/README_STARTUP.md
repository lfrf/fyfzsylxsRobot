# RobotMatch 启动脚本说明

## 📁 脚本文件

### 1. `start_robot_with_wakeword.sh` - 带唤醒词模式（推荐）
**功能**: 机器人待机，需要说唤醒词才开始监听

**唤醒词**: 
- "你好星仔"
- "你好小星"

**工作流程**:
```
待机 → 说唤醒词 → 唤醒确认 → 监听 → 对话 → 回复 → 10秒无语音返回待机
```

**使用场景**: 
- ✅ 日常使用（省电、减少误触发）
- ✅ 多人环境（避免误识别）
- ✅ 演示展示

**启动命令**:
```bash
bash scripts/start_robot_with_wakeword.sh
```

---

### 2. `start_robot_no_wakeword.sh` - 直接监听模式
**功能**: 机器人持续监听，检测到语音立即处理

**工作流程**:
```
持续监听 → 检测到语音 → 对话 → 回复 → 继续监听
```

**使用场景**: 
- ✅ 调试测试
- ✅ 单人环境
- ✅ 需要快速响应

**启动命令**:
```bash
bash scripts/start_robot_no_wakeword.sh
```

---

## 🚀 快速启动

### 前置条件

**1. 确保SSH隧道已建立**
```bash
# 在另一个终端运行
ssh -N \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -L 127.0.0.1:29000:127.0.0.1:19000 \
  -L 127.0.0.1:29001:127.0.0.1:20000 \
  -L 127.0.0.1:29002:127.0.0.1:20000 \
  -p 你的端口 root@你的服务器地址
```

**2. 确认隧道连通**
```bash
curl http://127.0.0.1:29000/health
curl http://127.0.0.1:29001/health
```

**3. 启动机器人**
```bash
# 带唤醒词（推荐）
bash scripts/start_robot_with_wakeword.sh

# 或不带唤醒词
bash scripts/start_robot_no_wakeword.sh
```

---

## 🎯 使用示例

### 带唤醒词模式

```bash
# 1. 启动机器人
bash scripts/start_robot_with_wakeword.sh

# 2. 等待启动完成，看到日志：
#    [wake-word-detector] started
#    [raspirobot] state=STANDBY

# 3. 说唤醒词
你: "你好星仔"
# 日志: wake_word_detected keyword=你好星仔
# 日志: state=WAKE_DETECTED → LISTENING

# 4. 听到确认音后，开始对话
你: "切换为关怀模式"
机器人: "好的，已切换到关怀模式..."

# 5. 继续对话
你: "我今天有点累"
机器人: "听起来你今天很辛苦..."

# 6. 10秒无语音后自动返回待机
# 日志: state=LISTENING → STANDBY
```

### 直接监听模式

```bash
# 1. 启动机器人
bash scripts/start_robot_no_wakeword.sh

# 2. 等待启动完成，看到日志：
#    [raspirobot] state=LISTENING

# 3. 直接说话（无需唤醒词）
你: "切换为关怀模式"
机器人: "好的，已切换到关怀模式..."

# 4. 继续对话
你: "我今天有点累"
机器人: "听起来你今天很辛苦..."
```

---

## ⚙️ 配置说明

### 唤醒词配置

**修改唤醒词**:
```bash
# 编辑关键词文件
nano models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/keywords.txt

# 格式：拼音 :分数 #阈值 @中文
# 示例：
n ǐ h ǎo x īng z ǎi :3.0 #0.08 @你好星仔
x iǎo w ǎ l ì :3.0 #0.08 @小瓦力
```

**调整灵敏度**:
- 阈值越低越敏感（容易误触发）
- 阈值越高越严格（可能漏检）
- 推荐范围: 0.05 ~ 0.15

**修改超时时间**:
```bash
# 在启动脚本中修改
export ROBOT_WAKE_WORD_TIMEOUT_S=15  # 唤醒后15秒无语音返回待机
```

### 音频设备配置

**查看可用设备**:
```bash
arecord -l  # 查看录音设备
aplay -l    # 查看播放设备
```

**修改设备**:
```bash
# 在启动脚本中修改
export ROBOT_AUDIO_CAPTURE_DEVICE=plughw:CARD=你的麦克风,DEV=0
export ROBOT_AUDIO_PLAYBACK_DEVICE=plughw:CARD=你的扬声器,DEV=0
```

---

## 🐛 故障排查

### 问题1: 唤醒词不响应

**检查模型文件**:
```bash
ls -lh models/sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20/
# 应该看到: encoder, decoder, joiner, tokens.txt, keywords.txt
```

**检查麦克风**:
```bash
arecord -D plughw:CARD=Lite,DEV=0 -f S16_LE -r 16000 -c 2 -d 3 test.wav
aplay test.wav
```

**查看日志**:
```bash
# 应该看到:
# wake_word_detector_started
# wake_word_detection_loop_started
```

### 问题2: 重复触发

**增加冷却时间**:
```bash
# 在启动脚本中修改
export ROBOT_WAKE_WORD_TIMEOUT_S=15
```

**提高检测阈值**:
```bash
# 编辑 keywords.txt，将 #0.08 改为 #0.12
```

### 问题3: 远程服务不通

**检查隧道**:
```bash
curl http://127.0.0.1:29000/health
# 应该返回: {"status":"ok",...}
```

**重建隧道**:
```bash
# 杀掉旧隧道
pkill -f "ssh.*29000"

# 重新建立
ssh -N -L 127.0.0.1:29000:127.0.0.1:19000 ...
```

### 问题4: 眼睛屏不显示

**检查SPI**:
```bash
ls /dev/spidev*
# 应该看到: /dev/spidev0.0, /dev/spidev1.0
```

**检查GPIO权限**:
```bash
sudo usermod -a -G spi,gpio pi
# 重新登录后生效
```

---

## 📊 性能优化

### 降低CPU占用

**使用int8量化模型**（已默认启用）:
```bash
# 在 wake_word_sherpa.py 中已配置
use_int8: bool = True
```

**减少线程数**:
```bash
# 修改 wake_word_sherpa.py
num_threads=1  # 从2改为1
```

### 降低延迟

**使用chunk-8模型**（已默认启用）:
```bash
chunk_size: int = 8  # 低延迟模式
```

**减少音频块大小**:
```bash
# 在 wake_word_sherpa.py 中
samples = mic.read(self.config.sample_rate // 20)  # 从//10改为//20
```

---

## 📝 日志说明

### 关键日志事件

**唤醒词相关**:
```
wake_word_detector_started          # 唤醒词引擎启动
wake_word_detection_loop_started    # 检测循环开始
wake_word_detected                  # 检测到唤醒词
wake_word_detector_stopped          # 引擎停止
```

**状态转换**:
```
state=STANDBY                       # 待机
state=WAKE_DETECTED                 # 唤醒检测
state=LISTENING                     # 监听中
state=SPEECH_DETECTED               # 检测到语音
state=PROCESSING                    # 处理中
state=PLAYING                       # 播放回复
```

**音频处理**:
```
listening_started                   # 开始监听
speech_started                      # 检测到语音开始
speech_ended                        # 语音结束
utterance_saved                     # 语音片段已保存
```

---

## 🎓 最佳实践

1. **日常使用**: 使用带唤醒词模式，省电且减少误触发
2. **调试测试**: 使用直接监听模式，快速验证功能
3. **定期检查**: 每天检查SSH隧道是否正常
4. **日志监控**: 观察日志中的错误和警告信息
5. **音量调节**: 根据环境调整扬声器音量（默认70%）

---

## 📞 获取帮助

如遇到问题，请检查：
1. 日志输出中的错误信息
2. SSH隧道是否正常
3. 远程服务是否都在运行
4. 音频设备是否正确配置
5. 模型文件是否完整

更多文档：
- `scripts/ROBOT_CHAIN_STARTUP.md` - 完整启动指南
- `scripts/ROBOTMATCH_REMOTE_RASPI_STARTUP_GUIDE.md` - 远程服务配置
- `README.md` - 项目总览
