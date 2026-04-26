# A22 v3 文件导读

本文档用于解释当前核心文件的职责，帮助快速理解这次新增的模块。

## 1. local/frontend

### `local/frontend/src/main.js`

前端总入口。

负责：

- 初始化页面
- 维护前端会话状态
- 组装 A/B/C 三栏界面
- 发送文本或音频请求
- 接收 remote 返回后更新聊天区、状态栏和数字人占位

### `local/frontend/src/api/chat.js`

前端请求封装层。

负责：

- 统一决定请求目标
- 默认调用 `/api/chat`
- 如果启用了直连模式，则使用 `VITE_API_BASE`
- 统一处理非 200 响应并抛出错误

### `local/frontend/src/ui/AvatarPanel.js`

数字人渲染占位组件。

负责：

- 渲染 2D 占位头像
- 显示 `emotion_style`
- 显示 `facial_expression`
- 显示 `head_motion`
- 根据 remote 返回更新头像状态

### `local/frontend/src/ui/ChatPanel.js`

聊天区组件。

负责：

- 渲染用户消息
- 渲染数字人回复
- 渲染系统消息
- 显示 loading 状态

### `local/frontend/src/ui/InputBar.js`

输入区组件。

负责：

- 文本输入
- 浏览器麦克风录音
- 将录音转换为 `base64`
- 管理“开始录音 / 停止录音 / 发送”

说明：

- 当前这是第一版音频输入骨架
- 已能把音频随请求发给后端
- 但还没有真正接入远端 ASR 模型

### `local/frontend/src/ui/StatusBar.js`

状态栏组件。

负责展示：

- 当前 `session_id`
- 下一轮 `turn_id`
- 请求传输状态
- remote 状态
- 输入模式
- 当前情绪风格
- 当前表情与头部动作
- 当前音频状态

### `local/frontend/src/styles.css`

前端样式表。

负责：

- 三栏布局
- 聊天消息样式
- 数字人占位样式
- 状态栏与输入区样式
- 响应式布局

### `local/frontend/vite.config.js`

Vite 开发配置。

负责：

- 监听 `0.0.0.0:3000`
- 配置 `/api` 代理到本地后端

这意味着：

- 你既可以通过 `nginx` 访问 `http://localhost`
- 也可以直接访问 `http://localhost:3000`

## 2. local/edge-backend

### `local/edge-backend/app.py`

边缘后端总入口。

负责：

- 创建 FastAPI 应用
- 注册 `health` 与 `chat` 路由

### `local/edge-backend/config.py`

运行配置读取模块。

负责：

- 读取 `CLOUD_API_BASE`
- 读取 remote 请求超时
- 读取日志目录和数据目录
- 读取默认会话前缀

### `local/edge-backend/models.py`

边缘后端数据模型定义。

负责：

- 定义前端传入的 `ChatRequest`
- 定义转发到 remote 的 `RemoteChatRequest`
- 定义 `ChatResponse`
- 定义错误响应与健康检查响应

### `local/edge-backend/routes/health.py`

健康检查路由。

负责：

- 返回当前后端状态
- 返回当前使用的 `cloud_api_base`
- 返回当前超时时间

### `local/edge-backend/routes/chat.py`

边缘侧核心业务入口。

负责：

- 接收前端 `/chat`
- 补齐 `session_id / turn_id`
- 调用请求归一化逻辑
- 调用 remote 转发客户端
- 处理远端异常
- 将最终结果返回给前端

### `local/edge-backend/services/session_service.py`

本地会话管理模块。

负责：

- 当请求里没有 `session_id` 时自动生成
- 当请求里没有 `turn_id` 时自动递增

说明：

- 当前是内存实现
- 容器重启后会丢失会话状态

### `local/edge-backend/services/input_preprocessor.py`

输入归一化模块。

负责：

- 统一文本与音频请求格式
- 校验“文本和音频至少有一个”
- 为纯音频请求补一个兼容文本占位
- 自动把 `input_type` 修正为 `audio`

### `local/edge-backend/services/orchestrator_client.py`

remote 转发客户端。

负责：

- 使用 `httpx` 请求 remote `/chat`
- 处理 timeout
- 处理 remote 非 200 错误
- 把 remote JSON 反序列化成 `ChatResponse`

它是当前 local 和 remote 真正打通的关键文件。

## 3. remote/orchestrator

### `remote/orchestrator/app.py`

远端 orchestrator 总入口。

负责：

- 创建 FastAPI 应用
- 注册 `health` 与 `chat` 路由

### `remote/orchestrator/models.py`

远端数据模型定义。

负责：

- 定义 remote 接收的请求格式
- 定义 remote 输出的结构化回复格式
- 定义健康检查与错误模型

### `remote/orchestrator/routes/health.py`

远端健康检查接口。

负责：

- 返回当前时间
- 返回当前 orchestrator 模式

### `remote/orchestrator/routes/chat.py`

远端聊天入口。

负责：

- 校验请求至少包含文本或音频
- 调用 `dialog_service`

### `remote/orchestrator/services/dialog_service.py`

远端主业务编排层。

负责：

- 调用 ASR adapter
- 读取历史会话摘要
- 调用策略层
- 调用 LLM adapter
- 调用 TTS adapter
- 拼装最终结构化响应

这是当前 remote 侧的核心调度文件。

### `remote/orchestrator/services/policy_service.py`

动作和情绪策略模块。

负责：

- 根据文本或音频轮次选择 `emotion_style`
- 根据语义判断选择 `avatar_action`

当前是规则驱动版本。

### `remote/orchestrator/services/session_state.py`

远端会话状态模块。

负责：

- 按 `session_id` 维护简单历史
- 返回最近几轮的摘要

当前是内存实现。

### `remote/orchestrator/adapters/asr_client.py`

ASR 占位适配器。

负责：

- 如果请求已有文本，直接使用文本
- 如果请求只有音频，返回占位转写结果

当前不是真实 ASR。

### `remote/orchestrator/adapters/llm_client.py`

LLM 占位适配器。

负责：

- 根据输入内容生成规则回复
- 对情绪词做简单判断
- 对音频轮次做简单分支
- 对历史摘要做简单引用

当前不是真实 LLM。

### `remote/orchestrator/adapters/tts_client.py`

TTS 占位适配器。

负责：

- 为后续语音合成预留接口

当前始终返回 `None`。

## 4. 基础设施文件

### `compose.local.yaml`

本地运行入口。

负责启动：

- `frontend`
- `edge-backend`
- `nginx`
- `gpu-tools`

### `compose.remote.yaml`

远端运行入口。

负责启动：

- `orchestrator`

### `infra/nginx/default.conf`

本地统一入口代理。

负责：

- `/` 转发到 `frontend:3000`
- `/api/` 转发到 `edge-backend:8000`

## 5. 这次新增文件的目的

你感觉“突然多了很多文件”，本质上是因为我把原来几个单文件拆成了标准模块结构。

### 拆分原因

- 让 local 和 remote 结构对称
- 让请求处理、配置、模型、服务逻辑分离
- 方便你后面接入真实 `ASR / LLM / TTS`
- 方便你和队友继续协作开发

### 记忆方法

你可以先只记住 6 个关键入口：

- `local/frontend/src/main.js`
- `local/frontend/src/api/chat.js`
- `local/edge-backend/routes/chat.py`
- `local/edge-backend/services/orchestrator_client.py`
- `remote/orchestrator/routes/chat.py`
- `remote/orchestrator/services/dialog_service.py`

只要先理解这 6 个文件，整条主链路就能看明白。
