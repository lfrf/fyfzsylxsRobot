# 0508 Design

## 1. 背景与目标
当前系统的状态机只有待机、唤醒、听写、上传、思考、播报等线性流程，无法清晰表达“唤醒后的准备阶段”和“工作态内的持续交互阶段”之间的边界。

本次设计目标是引入一个明确的中间态 `PREPARING`，但它**不承担语音输入处理**，只负责唤醒后的准备动作。准备完成后，系统应立即进入 `WORKING` 内部的 `LISTENING` 子阶段，从而让所有后续交互都归属在工作态中。

---

## 2. 状态模型

### 2.1 `STANDBY`
**职责**
- 程序启动后的默认状态
- 仅监听唤醒词
- 不启动视觉模块
- 不启动人脸追踪
- 不上传视频帧

**进入条件**
- 系统启动完成
- `PREPARING` 超时回退
- `WORKING` 超时回退

**退出条件**
- 检测到唤醒词，进入 `PREPARING`

**约束**
- 待机期间不得占用视觉链路
- 待机期间不得启动远程视频上传

---

### 2.2 `PREPARING`
**职责**
- 唤醒词触发后的短暂准备状态
- 启动视觉模块
- 启动人脸追踪
- 启动远程视频帧上传
- 触发远程人脸识别链路
- 完成准备后，立即切换到 `WORKING.LISTENING`

**明确约束**
- 不处理语音输入
- 不等待用户回答
- 不承担“首轮说话识别”职责
- 不在该状态内做对话闭环

**进入条件**
- `STANDBY` 检测到唤醒词

**退出条件**
- 准备完成后，立即进入 `WORKING.LISTENING`
- 若准备阶段本身出现异常，可回退到 `STANDBY`

**设计意图**
- `PREPARING` 只做“开机后准备交互环境”的工作
- 它是一个过渡层，不是输入等待层

---

### 2.3 `WORKING`
**职责**
- 正常交互的主状态
- 所有语音输入处理都发生在该状态内部
- 所有多轮对话都发生在该状态内部
- 每轮交互完成后，回到工作态内部的 `LISTENING`

**内部子阶段**
- `LISTENING`: 等待用户输入
- `RECORDING`: 录音中
- `UPLOADING`: 上送远端中
- `THINKING`: 远端思考中
- `SPEAKING`: 播报中

**进入条件**
- `PREPARING` 完成后进入 `WORKING.LISTENING`

**退出条件**
- `SPEAKING` 结束后回到 `WORKING.LISTENING`
- `WORKING.LISTENING` 连续 10 秒无语音输入，则退出到 `STANDBY`
- 发生系统错误时进入错误态

**关键约束**
- `SPEAKING` 结束后不能回到 `PREPARING`
- 预备阶段之后，所有交互都必须在 `WORKING` 内循环
- `WORKING.LISTENING` 是“工作态的等待输入子阶段”

---

## 3. 推荐的状态迁移图

```text
IDLE
  └─(启动完成)→ STANDBY

STANDBY
  └─(WakeWordDetected)→ PREPARING

PREPARING
  └─(准备完成)→ WORKING.LISTENING
  └─(准备失败/异常)→ STANDBY

WORKING.LISTENING
  ├─(SpeechStart)→ WORKING.RECORDING
  ├─(10s无输入)→ STANDBY
  └─(NewSpeechInput while busy)→ 忙提示/忽略

WORKING.RECORDING
  └─(SpeechEnd)→ WORKING.UPLOADING

WORKING.UPLOADING
  └─(RemoteRequestSent)→ WORKING.THINKING

WORKING.THINKING
  └─(RemoteResultReady)→ WORKING.SPEAKING

WORKING.SPEAKING
  └─(PlaybackDone)→ WORKING.LISTENING
```

---

## 4. 关键业务规则

### 4.1 待机规则
- 待机时只监听唤醒词
- 待机时不启动视觉模块
- 待机时不维护人脸追踪生命周期

### 4.2 预备规则
- 唤醒后立即进入 `PREPARING`
- `PREPARING` 必须尽快切换到 `WORKING.LISTENING`
- `PREPARING` 不等待语音输入
- `PREPARING` 不承担注册问询逻辑

### 4.3 工作规则
- 工作态内所有交互都走 `LISTENING -> RECORDING -> UPLOADING -> THINKING -> SPEAKING -> LISTENING`
- `SPEAKING` 结束后回到 `WORKING.LISTENING`
- `WORKING.LISTENING` 10 秒没有语音输入，直接退出回 `STANDBY`

### 4.4 视觉规则
- 视觉模块只允许在 `PREPARING` 中启动
- 视觉模块在回到 `STANDBY` 时停止
- 视觉模块和人脸追踪不依赖语音输入是否已经发生

---

## 5. 这次设计与后续需求的关系

本设计为后续的用户名注册流程预留了挂载点，但**用户名注册不应放在 `PREPARING` 内等待**。更合理的做法是：

1. `PREPARING` 只负责启动视觉与识别链路
2. 识别结果进入远程侧判断
3. `WORKING` 中的第一轮或后续轮次可以承接“用户名为空”的注册问询

也就是说，`PREPARING` 是准备层，不是注册等待层。

---

## 6. 需要实现的工程接口边界

### 6.1 状态机边界
- 明确新增 `PREPARING`
- 明确 `WORKING` 是一个复合工作态，而不是单一状态
- 保留 `LISTENING / RECORDING / UPLOADING / THINKING / SPEAKING` 作为工作态内部流程

### 6.2 runtime 边界
- 待机阶段只启动唤醒词监听
- 唤醒后先启动视觉，再迅速进入工作态监听
- 超时判定只在 `WORKING.LISTENING` 执行

### 6.3 视觉边界
- 视觉生命周期由 `PREPARING` 打开、由 `STANDBY` 关闭
- 不在待机阶段启动摄像头或上传任务

---

## 7. 验收标准

### 必须满足
1. 启动后默认处于 `STANDBY`
2. `STANDBY` 只监听唤醒词，不启动视觉
3. 唤醒后进入 `PREPARING`
4. `PREPARING` 不处理语音输入
5. `PREPARING` 完成后立即进入 `WORKING.LISTENING`
6. 后续所有交互都发生在 `WORKING` 内部
7. `WORKING.SPEAKING` 结束后回到 `WORKING.LISTENING`
8. `WORKING.LISTENING` 10 秒无输入后返回 `STANDBY`
9. 返回 `STANDBY` 时停止视觉和人脸追踪

### 不允许发生
- 待机状态启动视觉
- `PREPARING` 内等待用户说话
- 每轮对话后回到 `PREPARING`
- 10 秒超时后仍保留视觉链路运行

---

## 8. 实施优先级
1. 先落地状态机三段式边界
2. 再拆 runtime 中的待机/预备/工作职责
3. 再接入视觉生命周期控制
4. 最后接入用户名注册与远程识别闭环
