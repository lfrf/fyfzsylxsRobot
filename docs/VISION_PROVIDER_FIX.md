# Vision Provider 启动修复

## 问题描述

在启用唤醒词模式时，摄像头和人脸识别功能不工作。日志显示：
- ✅ `event=vision_provider_started_for_work_mode` - 视觉提供者已标记为启动
- ✅ `event=identity_watcher_started` - 身份监视器已启动
- ❌ 但没有实际的视频捕获和上传日志
- ❌ 没有人脸识别结果

## 根本原因

在 `raspirobot/main.py` 中存在两个相关的代码逻辑：

### 1. Vision Provider 启动逻辑（第 495-502 行）

```python
if wake_word_provider is None:  # ← 只有在没有唤醒词时才启动
    if hasattr(vision_provider, "start"):
        if face_tracking_lifecycle is not None and hasattr(vision_provider, "set_shared_camera_mode"):
            vision_provider.set_shared_camera_mode(True)
            logger.info("remote_vision_provider: shared_camera_mode enabled (face tracking will inject frames)")
        vision_provider.start()
    if face_tracking_lifecycle is not None:
        face_tracking_lifecycle.start()
```

### 2. Identity Watcher 配置（第 213-225 行）

```python
return IdentityWatcher(
    vision_provider=vision_provider,
    config=IdentityWatcherConfig(
        ...
        manage_vision_provider=False,  # ← 不管理 vision_provider 的启动
    ),
    on_identity_resolved=on_identity_resolved,
)
```

**问题**：
- 当启用唤醒词时，`vision_provider.start()` 不会在 main.py 中被调用
- `IdentityWatcher` 的 `manage_vision_provider=False`，所以它也不会启动 `vision_provider`
- 结果：`RemoteVisionContextProvider` 的后台线程从未启动，摄像头不捕获画面

## 解决方案

将 `IdentityWatcher` 的 `manage_vision_provider` 设置为 `True`，让它负责管理 `vision_provider` 的生命周期：

```python
return IdentityWatcher(
    vision_provider=vision_provider,
    config=IdentityWatcherConfig(
        ...
        manage_vision_provider=True,  # ✅ 修复：让 IdentityWatcher 管理 vision_provider
    ),
    on_identity_resolved=on_identity_resolved,
)
```

这样，当 `IdentityWatcher.start()` 被调用时（在状态转换到 LISTENING 时），它会：
1. 调用 `vision_provider.stop()`（如果已运行）
2. 调用 `vision_provider.set_shared_camera_mode(shared_camera_mode)`
3. 调用 `vision_provider.start()` - **启动后台捕获线程**

## 工作流程

### 修复前
```
唤醒词检测 → LISTENING 状态
  → IdentityWatcher.start() 被调用
  → manage_vision_provider=False，不启动 vision_provider
  → RemoteVisionContextProvider 的后台线程未运行
  → 摄像头不捕获画面 ❌
```

### 修复后
```
唤醒词检测 → LISTENING 状态
  → IdentityWatcher.start() 被调用
  → manage_vision_provider=True，启动 vision_provider ✅
  → RemoteVisionContextProvider.start() 被调用
  → 后台线程开始捕获和上传视频帧 ✅
  → Vision Service 返回人脸识别结果 ✅
  → 人脸追踪启动 ✅
```

## 预期日志

修复后，应该看到：

```
event=wake_word_detected
event=vision_provider_started_for_work_mode
event=identity_watcher_started
event=remote_vision_provider_started mode=own_camera  ← 新增
event=remote_vision_capture_loop_started  ← 新增
event=identity_watcher_face_resolved face_id=xxx  ← 新增
event=face_tracking_started  ← 新增
```

## 测试步骤

1. 在树莓派上重新启动机器人：
   ```bash
   cd /home/pi/Desktop/code/fyfzsylxsRobot
   source .venv/bin/activate
   bash scripts/start_robot_with_wakeword.sh
   ```

2. 说唤醒词："你好小星"

3. 出现在摄像头前

4. 检查日志中是否有：
   - `remote_vision_provider_started`
   - `remote_vision_capture_loop_started`
   - `identity_watcher_face_resolved`
   - `face_tracking_started`

## 相关文件

- `raspirobot/main.py` - 主启动逻辑
- `raspirobot/vision/identity_watcher.py` - 身份监视器
- `raspirobot/vision/remote_vision_provider.py` - 远程视觉提供者
- `raspirobot/core/runtime.py` - 运行时状态管理

## 修复日期

2026-05-07

## 修复人员

Kiro AI Assistant
