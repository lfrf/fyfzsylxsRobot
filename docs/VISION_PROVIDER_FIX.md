# Vision Provider 启动修复

## 问题描述

在启用唤醒词模式时，摄像头和人脸识别功能不工作。日志显示：
- ✅ `event=vision_provider_started_for_work_mode` - 视觉提供者已标记为启动
- ✅ `event=identity_watcher_started` - 身份监视器已启动
- ❌ 但没有实际的视频捕获和上传日志
- ❌ 没有人脸识别结果

## 根本原因

### 原因 1: IdentityWatcher 未管理 vision_provider（已修复）

在 `raspirobot/main.py` 中，`IdentityWatcher` 的 `manage_vision_provider=False`，导致 `vision_provider` 从未启动。

**修复**：将 `manage_vision_provider` 改为 `True`（commit 9b8df7a）

### 原因 2: 摄像头冲突（已修复）

当同时启用唤醒词和人脸追踪时：
1. `IdentityWatcher` 启动 `vision_provider`（独立摄像头模式）
2. 如果启用了人脸追踪，两者会竞争同一个摄像头
3. `vision_provider` 初始化失败，无法捕获视频

在 `raspirobot/core/runtime.py` 中，唤醒词检测后启动 `vision_provider` 时，总是使用 `shared_camera_mode=False`：

```python
self._start_vision_provider(shared_camera_mode=False)  # ← 总是独立模式
self._start_identity_watcher(shared_camera_mode=False)
```

但如果启用了人脸追踪，应该使用共享摄像头模式，避免冲突。

**修复**：根据是否启用人脸追踪，动态设置 `shared_camera_mode`（commit 354f595）

```python
# 如果启用了人脸追踪，使用共享摄像头模式，避免摄像头冲突
shared_camera = self.face_tracking_lifecycle is not None
self._start_vision_provider(shared_camera_mode=shared_camera)
self._start_identity_watcher(shared_camera_mode=shared_camera)
```

## 解决方案总结

### 修复 1: 让 IdentityWatcher 管理 vision_provider

**文件**: `raspirobot/main.py`

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

### 修复 2: 根据人脸追踪状态设置共享摄像头模式

**文件**: `raspirobot/core/runtime.py`

```python
# 如果启用了人脸追踪，使用共享摄像头模式，避免摄像头冲突
shared_camera = self.face_tracking_lifecycle is not None
self._start_vision_provider(shared_camera_mode=shared_camera)
self._start_identity_watcher(shared_camera_mode=shared_camera)
```

### 修复 3: 添加详细的启动日志

**文件**: `raspirobot/vision/remote_vision_provider.py`

添加了详细的日志，便于诊断问题：
- `remote_vision_provider_start_attempt`
- `remote_vision_provider_init_camera_start`
- `remote_vision_provider_init_camera_done`
- `remote_vision_provider_start_failed` (with exc_info=True)

## 工作流程

### 修复前
```
唤醒词检测 → LISTENING 状态
  → IdentityWatcher.start(shared_camera_mode=False)
  → vision_provider.start() 尝试打开摄像头
  → 如果人脸追踪已启动，摄像头被占用
  → 初始化失败，无日志 ❌
```

### 修复后
```
唤醒词检测 → LISTENING 状态
  → 检测到 face_tracking_lifecycle 存在
  → IdentityWatcher.start(shared_camera_mode=True) ✅
  → vision_provider.set_shared_camera_mode(True)
  → vision_provider.start() 使用共享模式，不打开摄像头 ✅
  → 等待人脸追踪注入帧 ✅
  → 人脸识别成功 ✅
```

## 预期日志

修复后，应该看到：

```
event=wake_word_detected
event=vision_provider_started_for_work_mode
event=identity_watcher_started shared_camera_mode=True  ← 注意这里是 True
event=remote_vision_provider_start_attempt shared_camera_mode=True  ← 新增
event=remote_vision_provider_started mode=shared_camera  ← 新增，注意是 shared_camera
event=remote_vision_inject_loop_started  ← 新增
event=identity_watcher_face_resolved face_id=xxx  ← 新增
event=face_tracking_enabled_after_identity  ← 新增
```

## 测试步骤

1. 在树莓派上更新代码：
   ```bash
   cd /home/pi/Desktop/code/fyfzsylxsRobot
   git pull
   ```

2. 重新启动机器人：
   ```bash
   source .venv/bin/activate
   bash scripts/start_robot_with_wakeword.sh
   ```

3. 说唤醒词："你好小星"

4. 出现在摄像头前

5. 检查日志中是否有：
   - `remote_vision_provider_start_attempt shared_camera_mode=True`
   - `remote_vision_provider_started mode=shared_camera`
   - `remote_vision_inject_loop_started`
   - `identity_watcher_face_resolved`
   - `face_tracking_enabled_after_identity`

## 相关文件

- `raspirobot/main.py` - 主启动逻辑，IdentityWatcher 配置
- `raspirobot/core/runtime.py` - 运行时状态管理，唤醒词处理
- `raspirobot/vision/identity_watcher.py` - 身份监视器
- `raspirobot/vision/remote_vision_provider.py` - 远程视觉提供者

## 修复历史

- **2026-05-07 (commit 9b8df7a)**: 修复 `manage_vision_provider=False` 问题
- **2026-05-07 (commit 354f595)**: 修复摄像头冲突问题，添加详细日志

## 修复人员

Kiro AI Assistant
