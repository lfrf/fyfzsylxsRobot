# Vision Provider 测试指南

## 测试目标

验证采用方案A（由 runtime 统一管理 vision_provider）后，唤醒词模式下摄像头和人脸识别是否正常工作。

**最新修复**（commit 2118e48）：将 `RemoteVisionContextProvider` 的日志改为使用 `log_event()`，解决日志不显示的问题。

## 测试步骤

### 1. 在树莓派上更新代码

```bash
cd /home/pi/Desktop/code/fyfzsylxsRobot
git pull
```

**预期输出**：
```
remote: Enumerating objects: 9, done.
...
Updating 16e01ae..2118e48
Fast-forward
 raspirobot/vision/remote_vision_provider.py | 53 ++++++++++++++--------------
 1 file changed, 27 insertions(+), 26 deletions(-)
```

### 2. 确认 SSH 隧道已连接

在树莓派上检查隧道是否已建立：

```bash
# 检查隧道进程
ps aux | grep ssh | grep 29000

# 测试端口连通性
curl -s http://127.0.0.1:29000/health || echo "隧道未连接"
```

**如果隧道未连接**，重新建立：

```bash
ssh -N \
  -L 127.0.0.1:29000:127.0.0.1:19000 \
  -L 127.0.0.1:29001:127.0.0.1:20000 \
  -L 127.0.0.1:29002:127.0.0.1:19200 \
  -p 42706 root@connect.bjb1.seetacloud.com
```

### 3. 启动机器人

```bash
source .venv/bin/activate
bash scripts/start_robot_with_wakeword.sh
```

### 4. 测试唤醒词和人脸识别

1. **说唤醒词**："你好小星"
2. **出现在摄像头前**（确保脸部清晰可见）
3. **观察日志输出**

## 预期日志（成功）

### 关键日志 1: runtime 启动 vision_provider

```
event=wake_word_detected keyword=你好小星
event=runtime_start_vision_provider shared_camera_mode=True provider_type=RemoteVisionContextProvider provider_id=140733660592784
```

### 关键日志 2: RemoteVisionContextProvider 启动

**这是最关键的日志，之前完全没有出现！**

```
event=remote_vision_provider_stop_called _running=False
event=remote_vision_provider_start_called _running=False shared_camera_mode=True
event=remote_vision_provider_start_attempt shared_camera_mode=True
event=remote_vision_provider_started mode=shared_camera ingest_url=http://127.0.0.1:29001/v1/video/ingest
event=remote_vision_inject_loop_started
```

### 关键日志 3: IdentityWatcher 启动（不管理 provider）

```
event=identity_watcher_restart_provider_start shared_camera_mode=True has_stop=True has_set_shared=True has_start=True provider_type=RemoteVisionContextProvider
event=identity_watcher_calling_provider_stop
event=identity_watcher_provider_stopped
event=identity_watcher_calling_provider_set_shared_mode shared_camera_mode=True
event=identity_watcher_provider_shared_mode_set shared_camera_mode=True
event=identity_watcher_calling_provider_start
event=identity_watcher_provider_started
event=identity_watcher_started shared_camera_mode=True poll_interval_s=1.0
```

### 关键日志 4: 人脸识别成功

```
event=identity_watcher_face_resolved face_id=xxx user_id=xxx persisted=True
event=face_tracking_enabled_after_identity face_id=xxx
```

## 问题诊断

### 问题 1: 仍然没有 `remote_vision_provider_start_called` 日志

**可能原因**：
1. `RemoteVisionContextProvider` 的 logger 配置问题
2. 树莓派上的代码版本不正确
3. `vision_lifecycle` 对象不是 `RemoteVisionContextProvider` 实例

**诊断步骤**：

1. 确认代码版本：
   ```bash
   cd /home/pi/Desktop/code/fyfzsylxsRobot
   git log --oneline -1
   # 应该显示: 16e01ae fix: 采用方案A - 由runtime统一管理vision_provider
   ```

2. 检查 `main.py` 中的 `manage_vision_provider`：
   ```bash
   grep -A 2 "manage_vision_provider" raspirobot/main.py
   # 应该显示: manage_vision_provider=False,  # 由 runtime 统一管理 vision_lifecycle
   ```

3. 添加临时调试日志（如果仍然失败）：
   在 `raspirobot/core/runtime.py` 的 `_start_vision_provider` 方法中添加：
   ```python
   def _start_vision_provider(self, *, shared_camera_mode: bool) -> None:
       if self.vision_lifecycle is None:
           log_event("vision_lifecycle_is_none", level="warning")  # ← 添加这行
           return
       # ... 其余代码
   ```

### 问题 2: `remote_vision_provider_start_called` 出现，但 `start()` 直接返回

**可能原因**：`_running=True`，导致 `start()` 方法直接返回

**解决方案**：在 `RemoteVisionContextProvider.start()` 开头添加强制重置：

```python
def start(self) -> None:
    logger.info("remote_vision_provider_start_called _running=%s shared_camera_mode=%s", self._running, self._shared_camera_mode)
    
    # 强制重置（临时调试）
    if self._running:
        logger.warning("remote_vision_provider_force_reset: _running was True, resetting to False")
        self._running = False
    
    # ... 其余代码
```

### 问题 3: 摄像头初始化失败

**日志特征**：
```
event=remote_vision_provider_start_attempt shared_camera_mode=False
event=remote_vision_provider_init_camera_start
event=remote_vision_provider_start_failed error=...
```

**可能原因**：
- 摄像头被其他进程占用
- 摄像头硬件问题（线松了）

**解决方案**：
1. 检查摄像头连接：
   ```bash
   vcgencmd get_camera
   # 应该显示: supported=1 detected=1
   ```

2. 测试摄像头：
   ```bash
   libcamera-hello --timeout 2000
   ```

3. 如果摄像头被占用，重启树莓派：
   ```bash
   sudo reboot
   ```

## 成功标志

✅ 看到 `remote_vision_provider_started mode=shared_camera`
✅ 看到 `remote_vision_inject_loop_started`
✅ 看到 `identity_watcher_face_resolved face_id=xxx`
✅ 看到 `face_tracking_enabled_after_identity`
✅ 舵机开始转动，追踪人脸

## 失败标志

❌ 没有 `remote_vision_provider_start_called` 日志
❌ 有 `remote_vision_provider_start_called` 但没有 `remote_vision_provider_started`
❌ 有 `remote_vision_provider_start_failed` 错误日志
❌ 唤醒后 10 秒超时，直接返回 STANDBY

## 下一步

如果测试成功，继续测试完整流程：
1. 唤醒 → 人脸识别 → 人脸追踪 → 对话 → 返回待机
2. 验证多次唤醒是否稳定
3. 验证人脸追踪是否流畅

如果测试失败，根据日志诊断问题，可能需要：
1. 添加更多调试日志
2. 检查 `vision_lifecycle` 对象的类型和状态
3. 检查摄像头硬件连接

## 相关文件

- `raspirobot/main.py` - IdentityWatcher 配置
- `raspirobot/core/runtime.py` - runtime 管理 vision_provider
- `raspirobot/vision/remote_vision_provider.py` - RemoteVisionContextProvider 实现
- `docs/VISION_PROVIDER_FIX.md` - 修复历史和原因分析
