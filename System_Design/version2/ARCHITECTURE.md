# A22 System Design v2

## 1. 当前版本定位

本版本用于记录 **A22 项目在“本地骨架 + 远端 orchestrator v0 + SSH 隧道”阶段** 的系统设计与阶段性结果。

当前系统已经完成：

- 本地 `local/frontend`、`local/edge-backend`、`nginx` 的 Docker Compose 骨架
- 远端 `remote/orchestrator` 的 `uv + Python 3.11 + uvicorn` 运行方式
- SSH 隧道转发：本地 `127.0.0.1:19000` -> 远端 `127.0.0.1:19000`
- `GET /health` 与 `POST /chat` 的 v0 协议验证

当前系统**尚未完成**：

- `local/edge-backend` 到远端 `orchestrator` 的真实 HTTP 转发接入
- 前端数字人展示层
- 前端消息与数字人控制逻辑的正式联动
- 远端真正的 LLM / RAG / TTS / 多模态推理

换句话说，当前已经搭好的是**系统骨架与远端通信基础设施**，但还没有完成**前端 -> 本地边缘后端 -> 远端 orchestrator -> 前端展示**的完整业务闭环。

---

## 2. 当前总体架构

```text
Windows
  ├─ VS Code / Cursor
  ├─ Browser
  └─ Docker Desktop

WSL2 Ubuntu 22.04
  ├─ local/frontend
  ├─ local/edge-backend
  ├─ nginx
  ├─ shared/contracts
  └─ SSH tunnel client

Remote Ubuntu Server
  └─ remote/orchestrator
```

### 2.1 职责划分

#### Windows

- 作为开发入口与展示入口
- 浏览器访问本地 `http://localhost`

#### WSL2 + Docker

- 承载本地源码与本地服务
- 运行 `frontend`、`edge-backend`、`nginx`
- 维护与实验室服务器之间的 SSH 隧道

#### Remote Server

- 运行 `remote/orchestrator`
- 后续承接 LLM、RAG、TTS、多模态等模块

---

## 3. 当前目录结构

```text
A22/
├─ local/
│  ├─ frontend/
│  ├─ edge-backend/
│  └─ README.md
├─ remote/
│  ├─ README.md
│  └─ orchestrator/
│     ├─ app.py
│     ├─ pyproject.toml
│     ├─ requirements.txt
│     ├─ .python-version
│     └─ README.md
├─ shared/
│  ├─ contracts/
│  └─ README.md
├─ infra/
├─ logs/
├─ data/
├─ compose.yaml
├─ compose.local.yaml
├─ compose.remote.yaml
├─ README.md
└─ ARCHITECTURE.md
```

---

## 4. 当前已验证的两条链路

### 4.1 本地 UI/边缘骨架链路

当前已完成：

- 浏览器 -> `nginx` -> `frontend`
- 浏览器 -> `nginx` -> `edge-backend`
- 本地 `curl http://localhost:8000/health`
- 本地 `curl http://localhost/api/chat`

说明：本地骨架已经成立。

### 4.2 本地到远端 SSH 隧道路由链路

当前已完成：

- SSH 登录实验室服务器
- 远端 `remote/orchestrator` 使用 `uv` 成功启动
- 本地 SSH 隧道建立成功
- 本地 `curl http://127.0.0.1:19000/health`
- 本地 `curl http://127.0.0.1:19000/chat`

说明：远端服务与 SSH 隧道链路已经成立。

---

## 5. 当前还没有完全打通的部分

虽然远端 `/chat` 已经能返回结果，但当前 `local/edge-backend` 还是本地 mock 返回，还没有真正向远端发起请求。

因此，当前状态应理解为：

### 已打通

```text
浏览器 -> nginx -> frontend
浏览器 -> nginx -> local/edge-backend
本地终端 -> SSH tunnel -> remote/orchestrator
```

### 尚未打通

```text
frontend
  -> local/edge-backend
  -> remote/orchestrator
  -> local/edge-backend
  -> frontend
```

这一步是当前系统从“骨架阶段”进入“联调阶段”的关键节点。

---

## 6. 当前接口状态（v0）

当前 v0 契约已经落在：

- `shared/contracts/api_v1.md`
- `shared/contracts/chat_request.example.json`
- `shared/contracts/chat_response.example.json`

当前统一接口为：

- `GET /health`
- `POST /chat`

请求示例：

```json
{
  "session_id": "demo-001",
  "turn_id": 1,
  "user_text": "你好我今天不开心",
  "input_type": "text",
  "client_ts": 1710000000
}
```

响应示例：

```json
{
  "server_status": "ok",
  "reply_text": "我在，你可以慢慢说。",
  "emotion_style": "gentle",
  "avatar_action": {
    "facial_expression": "soft_concern",
    "head_motion": "slow_nod"
  },
  "server_ts": 1710000001
}
```

---

## 7. 远端运行方式（当前选择）

由于实验室服务器当前用户没有 Docker daemon 权限，因此远端当前采用：

- `uv`
- `remote/orchestrator/.venv`
- `uv run uvicorn app:app --host 127.0.0.1 --port 19000`

这是一种**部署降级**而不是**架构变更**：

- 架构上仍保留 `compose.remote.yaml`
- 当前运行方式改为 `uv`
- 后续若 Docker 权限恢复，可切回远端 Compose

---

## 8. 后续模块扩展原则

如果未来 `remote/` 下新增服务，推荐结构如下：

```text
remote/
├─ orchestrator/
├─ llm-service/
├─ rag-service/
├─ tts-service/
└─ state-estimator/
```

每个远端服务建议：

- 各自拥有自己的目录
- 各自拥有自己的 `.venv`
- 各自拥有自己的 `pyproject.toml` 或依赖文件

不建议：

- 在 `remote/` 根目录下共用一个大而混杂的 `.venv`

---

## 9. 下一阶段开发重点

当前最应该优先推进的是 **local 部分的产品化与联调闭环**。

建议顺序如下：

1. `local/edge-backend` 改成真实调用 `CLOUD_API_BASE`
2. 前端消息发送改成完整对话流
3. 前端增加聊天记录、状态栏、动作标签显示
4. 前端数字人形象与控制逻辑接入
5. 远端 orchestrator 从固定回复升级为规则/模板驱动，再逐步接入真实推理

---

## 10. 当前结论

当前 A22 项目可以认为：

- **系统架构已经搭起来了**
- **本地骨架已经成立**
- **远端 orchestrator 运行方式已经成立**
- **本地与远端的 SSH 隧道通信已经成立**

但还不能说“完整业务管线已经全部打通”，因为 `local/edge-backend` 还没有真正把前端输入转发到远端 orchestrator。

所以，当前最准确的判断是：

**你已经完成了系统骨架与远端通信基础设施，下一步要做的是把 local 的真实业务流接到 remote 上。**
