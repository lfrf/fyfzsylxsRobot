# AutoDL HTTP 联调说明

## 目标

本说明用于记录当前项目在 **AutoDL 无卡模式** 下，如何通过 **HTTP + AutoDL 自定义服务代理** 打通：

- 本地前端 `local/frontend`
- 远端后端 `remote/orchestrator`

当前这套方案：

- 使用 **HTTP**
- **不使用 WebSocket**
- **不使用 SSH 隧道**
- 暂时**不启动** `avatar-service`

适用场景：

- 先验证本地前端和远端 `orchestrator` 是否连通
- 先跑通文本对话链路
- 当前机器资源不足，无法稳定启动 EchoMimic / TTS 重服务

---

## 当前链路

```text
本地浏览器
-> localhost:3000
-> Vite dev server
-> /api/chat
-> Vite proxy
-> AutoDL 自定义服务公网地址
-> proxy_in_instance
-> remote orchestrator:19000
```

---

## 一、远端启动 orchestrator

在 AutoDL 服务器终端执行：

```bash
cd ~/autodl-tmp/a22/code/A22_wmzjbyGroup/remote/orchestrator
source .venv/bin/activate

export AVATAR_SERVICE_ENABLED=false

python -m uvicorn app:app --host 0.0.0.0 --port 19000
```

成功标志：

```text
Uvicorn running on http://0.0.0.0:19000
```

注意：

- 这里启动的是 `remote/orchestrator`
- 不是 `remote/avatar-service`
- 当前是轻量模式，所以显式关闭：
  - `AVATAR_SERVICE_ENABLED=false`

---

## 二、远端验证 orchestrator 是否可用

新开一个远端终端，执行：

```bash
curl http://127.0.0.1:19000/health
```

预期返回类似：

```json
{"status":"ok", "...":"..."}
```

继续测试聊天接口：

```bash
curl -X POST http://127.0.0.1:19000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-test","turn_id":1,"input_mode":"text","user_text":"你好"}'
```

注意：

- 字段必须是 `user_text`
- 不是 `text`

预期返回：

- `reply_text`
- `response_source: "mock"`

---

## 三、下载并启动 AutoDL 代理工具

在远端终端执行：

```bash
cd ~
wget https://autodl-public.ks3-cn-beijing.ksyuncs.com/tool/api-proxy/proxy_in_instance
chmod +x proxy_in_instance
```

---

## 四、创建代理配置文件

在远端创建 `/root/config.yaml`：

```bash
cat > ~/config.yaml <<'EOF'
proxies:
  - host_and_port: http://127.0.0.1:19000
    route_path: /chat

  - host_and_port: http://127.0.0.1:19000
    route_path: /health

  - host_and_port: http://127.0.0.1:19000
    route_path: /chat/*

  - host_and_port: http://127.0.0.1:19000
    route_path: /health/*
EOF
```

文件位置：

- `/root/config.yaml`

注意：

- `route_path: /chat*` 是错误写法
- 必须写成：
  - `/chat`
  - `/chat/*`
- 否则 `proxy_in_instance` 会 panic

---

## 五、启动代理工具

在远端终端执行：

```bash
cd ~
./proxy_in_instance
```

正常情况下会看到类似输出：

```text
Proxy: http://127.0.0.1:6006/chat to http://127.0.0.1:19000/chat
Proxy: http://127.0.0.1:6006/health to http://127.0.0.1:19000/health
```

说明：

- 代理程序在容器内监听 `127.0.0.1:6006`
- 再把 `/chat`、`/health` 转发给 `orchestrator:19000`

这个窗口不要关闭。

---

## 六、远端验证代理是否工作

新开一个远端终端，执行：

```bash
curl http://127.0.0.1:6006/health
```

再执行：

```bash
curl -X POST http://127.0.0.1:6006/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-test","turn_id":1,"input_mode":"text","user_text":"你好"}'
```

如果这两条都通，说明：

- `proxy_in_instance`
- `orchestrator`
- 容器内 HTTP 转发

都已正常工作。

---

## 七、找到 AutoDL 自定义服务公网地址

在 AutoDL 实例页面中：

1. 进入实例详情页
2. 点击 `自定义服务`
3. 找到：
   - `http://127.0.0.1:6006 -> https://...`

当前实例的已验证公网入口示例：

```text
https://u949374-t70g-6daa853a.bjb1.seetacloud.com:8443
```

注意：

- 这里要选的是 **6006 对应的公网地址**
- 不是 SSH 地址
- 不是 JupyterLab 地址

---

## 八、本地验证公网地址

在本地浏览器打开：

```text
https://u949374-t70g-6daa853a.bjb1.seetacloud.com:8443/health
```

如果能返回 JSON，说明：

- 公网代理入口已打通
- 不需要 SSH 隧道

---

## 九、本地启动前端

在 **本地 Windows 终端** 执行。

### PowerShell

```powershell
cd D:\a22\FuChuangSai_A22\local\frontend
$env:VITE_API_PROXY_TARGET="https://u949374-t70g-6daa853a.bjb1.seetacloud.com:8443"
npm.cmd run dev
```

### CMD

```cmd
cd /d D:\a22\FuChuangSai_A22\local\frontend
set VITE_API_PROXY_TARGET=https://u949374-t70g-6daa853a.bjb1.seetacloud.com:8443
npm.cmd run dev
```

成功后访问：

```text
http://localhost:3000
```

---

## 十、如何验证本地前端已经连上远端 orchestrator

1. 打开浏览器开发者工具 `F12`
2. 切到 `Network`
3. 输入一句：
   - `你好`
4. 点击 `Send`

如果看到：

- `/api/chat`
- 状态码 `200`

同时页面出现 mock 回复，例如：

```text
你好，我已经收到你的消息了。当前是 remote orchestrator 的 mock LLM 回复。
```

则说明：

- 本地前端
- Vite 代理
- AutoDL 自定义服务
- 远端 `orchestrator`

已经全部打通。

---

## 常见错误与说明

### 1. 在远端 Linux 终端执行了本地 Windows 命令

错误示例：

```bash
cd D:\a22\FuChuangSai_A22\local\frontend
$env:VITE_API_PROXY_TARGET=...
npm.cmd run dev
```

原因：

- 这是 Windows 命令
- 只能在本地 PowerShell / CMD 执行

---

### 2. `curl /chat` 返回：

```json
{"detail":"Either user_text or audio input is required."}
```

原因：

- 请求体用了 `text`
- 正确字段是 `user_text`

---

### 3. `proxy_in_instance` 启动 panic

错误类似：

```text
panic: no / before catch-all in path '/chat*any'
```

原因：

- `config.yaml` 中写了：
  - `/chat*`

正确写法：

- `/chat`
- `/chat/*`

---

### 4. `avatar-service` 启动后直接 `Killed`

原因：

- 当前无卡模式资源不足
- `avatar-service` 启动时会加载重模型
- 进程很可能被系统 OOM 杀掉

当前阶段解决策略：

- 不启动 `avatar-service`
- 先只打通 `frontend -> orchestrator`

---

### 5. `favicon.ico 404`

这个可以忽略，不影响主链路联调。

---

## 当前结论

当前已经验证成功的是：

- 本地前端通过 HTTP 模式
- 经 Vite 代理
- 走 AutoDL 自定义服务公网地址
- 打到远端 `orchestrator`

这条链路已经打通。

当前尚未启用的部分：

- `avatar-service`
- TTS
- EchoMimic 视频生成

等有更合适的资源环境后，再继续接入。
