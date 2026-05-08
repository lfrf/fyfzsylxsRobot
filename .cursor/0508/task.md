# 0508 Task Plan

## Task 1：状态机三段式重构
### 目标
建立 `STANDBY -> PREPARING -> WORKING` 的三段式主状态结构。

### 任务内容
- 新增 `PREPARING` 状态
- 明确 `STANDBY` 只负责唤醒词监听
- 明确 `PREPARING` 只负责准备动作，不负责语音输入
- 明确 `WORKING` 承接所有对话交互
- 保留 `LISTENING / RECORDING / UPLOADING / THINKING / SPEAKING` 作为工作态内部流程

### 交付标准
- 状态命名和职责边界清晰
- 不同状态之间没有职责重叠
- 日志可区分三段主状态

---

## Task 2：runtime 与视觉生命周期拆分
### 目标
让视觉模块只在 `PREPARING` 期间启动，在回到 `STANDBY` 时停止。

### 任务内容
- 待机阶段不启动视觉
- 唤醒后进入 `PREPARING`
- 在 `PREPARING` 中启动视觉、人脸追踪、远程视频上传
- 准备完成后立即切换到 `WORKING.LISTENING`
- 返回 `STANDBY` 时关闭视觉和追踪

### 交付标准
- 待机不占用摄像头
- 预备状态可快速拉起视觉链路
- 退出工作态后视觉资源正确释放

---

## Task 3：工作态输入循环与超时回退
### 目标
让所有语音交互都发生在 `WORKING` 内部，并在空闲时自动回到待机。

### 任务内容
- `PREPARING` 完成后进入 `WORKING.LISTENING`
- `SPEAKING` 结束后回到 `WORKING.LISTENING`
- 在 `WORKING.LISTENING` 中实现 10 秒无输入回待机
- 为后续用户名注册、远程识别欢迎语流程预留接口

### 交付标准
- 工作态内可连续多轮交互
- 工作态空闲超时后可正确回到待机
- 不会错误地回到 `PREPARING`
