# A22 v3 运行入口与测试方法

本文档说明当前版本如何启动、如何测试，以及应该看什么效果。

## 1. 运行前必须确认的配置

### 1.1 Remote 要先可访问

当前 `local/edge-backend` 会把请求转发到 `CLOUD_API_BASE`，所以你必须先保证 remote `/chat` 能访问。

可选两种方式：

- 方式 A：远端服务器用 `uvicorn` 运行，然后通过 SSH 隧道暴露到本地
- 方式 B：本机临时用 `compose.remote.yaml` 跑一个 dry-run remote

### 1.2 `compose.local.yaml` 里的 `CLOUD_API_BASE` 不能保持占位值

当前文件里这一项还是占位：

```yaml
CLOUD_API_BASE: http://replace-with-remote-server
```

如果你不改它，本地后端虽然能启动，但请求 remote 时会失败。

### 推荐值

如果你已经把 SSH 隧道开在本机：

```text
127.0.0.1:19000 -> remote 127.0.0.1:19000
```

那么推荐把 `compose.local.yaml` 里的 `CLOUD_API_BASE` 改成：

```yaml
CLOUD_API_BASE: http://host.docker.internal:19000
```

原因：

- `edge-backend` 是运行在 Docker 容器里的
- 容器访问宿主机 SSH 隧道入口时，通常应该走 `host.docker.internal`

## 2. 运行入口

### 2.1 启动 remote

#### 方案 A：远端服务器 + SSH 隧道

在远端服务器：

```bash
cd /home/siyuen/docker_ws/A22/remote/orchestrator
source .venv/bin/activate
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

在本地 WSL 开 SSH 隧道：

```bash
ssh -N -L 19000:127.0.0.1:19000 <your-remote-user>@<your-remote-host>
```

#### 方案 B：本机 dry-run remote

在 `/home/siyuen/docker_ws/A22`：

```bash
docker compose -f compose.yaml -f compose.remote.yaml up -d orchestrator
```

如果用这个方案，你可以把 `CLOUD_API_BASE` 直接改成：

```yaml
CLOUD_API_BASE: http://host.docker.internal:19000
```

## 3. 启动 local

在 `/home/siyuen/docker_ws/A22`：

```bash
docker compose -f compose.yaml -f compose.local.yaml up -d
```

查看状态：

```bash
docker compose -f compose.yaml -f compose.local.yaml ps
```

查看日志：

```bash
docker compose -f compose.yaml -f compose.local.yaml logs -f
```

## 4. 浏览器入口

### 推荐入口

```text
http://localhost
```

这是经 `nginx` 的完整入口。

### 其他入口

- `http://localhost:3000`：前端 Vite 开发服务
- `http://localhost:8000/health`：本地边缘后端健康检查

## 5. 最小测试方法

### 5.1 先测 remote 是否可达

如果你走 SSH 隧道方案：

```bash
curl http://127.0.0.1:19000/health
```

预期：

- 返回 `status=ok`
- 返回 `orchestrator_mode=rule-based-v0`

### 5.2 测 local edge-backend 是否配置正确

```bash
curl http://localhost:8000/health
```

预期：

- 返回 `status=ok`
- 返回你实际配置的 `cloud_api_base`
- 返回 `request_timeout_seconds`

注意：

- 如果这里看到的 `cloud_api_base` 还是 `http://replace-with-remote-server`
- 说明你还没有改好 local 转发目标

### 5.3 测完整文本链路

```bash
curl -X POST http://localhost/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"你好，我今天有点难过","input_type":"text"}'
```

预期响应中应包含：

- `server_status`
- `reply_text`
- `emotion_style`
- `avatar_action`
- `input_mode`

并且情绪词场景下，通常会看到：

- `emotion_style: gentle`
- `avatar_action.facial_expression: soft_concern`
- `avatar_action.head_motion: slow_nod`

### 5.4 测浏览器效果

打开：

```text
http://localhost
```

你应该能看到：

- 左侧 A 区：2D 数字人占位头像
- 中间 B 区：聊天记录区
- 右侧 C 区：状态栏和输入区

发送文本后应观察：

- 聊天区新增用户消息
- 聊天区新增数字人回复
- 状态栏更新 `session / turn / emotion / action`
- 左侧数字人表情和头部动作状态更新

## 6. 音频测试方法

### 浏览器测试

在 `http://localhost`：

1. 点击 `Start audio capture`
2. 说一小段话
3. 点击 `Stop audio capture`
4. 点击 `Send turn`

预期：

- 页面提示已附加音频
- 请求能够发到 `edge-backend`
- remote 返回音频轮次的规则回复
- 状态栏中的 `Input mode` 变成 `audio`

### 当前已知限制

- 现在只是第一版音频输入骨架
- 没有真实语音识别模型
- 远端当前会走 placeholder ASR 逻辑

## 7. 我建议你优先看的运行结果

如果你只想快速判断这次改动有没有成功，优先看这 4 个点：

1. `curl http://localhost:8000/health`
2. `curl -X POST http://localhost/api/chat ...`
3. 浏览器里的三栏页面是否正常显示
4. 文本发送后左侧数字人状态是否有变化

## 8. 当前最容易踩坑的地方

### 坑 1：`CLOUD_API_BASE` 没改

现象：

- 前端能打开
- 但发送消息时报 remote 不可达

### 坑 2：SSH 隧道只在宿主机 `127.0.0.1`，容器访问不到

现象：

- 本机 `curl http://127.0.0.1:19000/health` 正常
- 但容器里的 `edge-backend` 还是请求失败

优先检查：

- `compose.local.yaml` 中是否用了 `host.docker.internal`

### 坑 3：只访问 `localhost:3000`，忘了 API 代理或 nginx 路径

当前已经在 `vite.config.js` 加了 `/api` 代理，但推荐你优先使用：

```text
http://localhost
```

这样最接近真实完整链路。
