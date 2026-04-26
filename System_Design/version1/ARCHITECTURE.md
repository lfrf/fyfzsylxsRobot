# A22 系统架构说明

本文档描述 **当前阶段** 的系统分层、本地 Docker Compose 组成、与实验室服务器之间的连接方式，以及后续演进方向。环境与复现步骤见根目录 `README.md`。

---

## 1. 文档范围与版本

- **适用对象**：本地开发（WSL2 + Docker Desktop）与实验室服务器（SSH 可达）联调。
- **当前阶段**：本地非推理链路已打通；实验室侧已通过 SSH 隧道验证 HTTP 往返；正式推理服务以远程部署为主。

---

## 2. 总体架构（三层）

```text
┌─────────────────────────────────────────────────────────────┐
│ Windows (开发入口与展示层)                                   │
│  - IDE: VS Code / Cursor                                     │
│  - 浏览器访问本地服务 (localhost)                             │
│  - Docker Desktop (WSL2 后端)                                │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ WSL2 Ubuntu 22.04 (本地 Linux 工作区与运行层)                │
│  - 项目源码位于 Linux 文件系统 (推荐 ~/docker_ws/A22)       │
│  - 源码分层: local/ (边缘) · remote/ (远端) · shared/ (协议) │
│  - Docker Compose 管理: frontend / edge-backend / nginx       │
│  - 可选: gpu-tools (GPU 链路验证，非主业务)                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            │ SSH 隧道 (可选，用于访问实验室 HTTP)
                            │ 例: 本地 127.0.0.1:19000 -> 远端 127.0.0.1:19000
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 实验室 / 远程服务器 (推理与编排层)                          │
│  - Ubuntu (当前环境为 20.04 LTS 等，以实际机器为准)        │
│  - 全部重推理: LLM、RAG、TTS、多模态融合、状态估计等         │
│  - 对外 HTTP 建议通过本机回环 + SSH 隧道或内网策略暴露     │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 职责划分（核心约定）

| 层级 | 职责 | 不负责 |
|------|------|--------|
| Windows | 编辑、调试、浏览器展示 | 不作为业务服务运行环境 |
| WSL2 + Docker | 前端页面、边缘网关、会话与转发、本地日志与缓存 | 大模型与重推理 |
| 远程服务器 | 推理编排、LLM、知识库、TTS 等 | 本地 UI 与设备直连（可选后续扩展） |

**约定**：所有**正式推理**部署在远程；本地仅负责**展示、边缘网关、预处理、转发与协议适配**。

### 2.2 仓库目录（根目录）

```text
A22/
├─ local/                 # 边缘侧：frontend、edge-backend
├─ remote/                # 远端侧：orchestrator 等
├─ shared/contracts/      # v0 协议与示例 JSON（双方对齐）
├─ infra/                 # nginx 等与两侧相关的配置
├─ compose.yaml
├─ compose.local.yaml     # 本地栈
├─ compose.remote.yaml    # 远端栈（在服务器上使用）
└─ README.md / ARCHITECTURE.md
```

---

## 3. 本地运行时架构（Docker Compose）

本地使用 **Docker Desktop + WSL2**，通过 **Compose 多文件合并** 启动：

- `compose.yaml`：项目名、网络、`named volumes`（日志与数据）。
- `compose.local.yaml`：本地服务定义。

启动命令：

```bash
docker compose -f compose.yaml -f compose.local.yaml up -d
```

### 3.1 服务清单

| 服务名 | 镜像 | 端口 | 说明 |
|--------|------|------|------|
| `frontend` | `node:20-bookworm-slim` | `3000` | 前端开发服务（Vite），页面与交互入口。 |
| `edge-backend` | `python:3.11-slim-bookworm` | `8000` | 边缘后端：FastAPI，会话、转发、调用远端预留。 |
| `nginx` | `nginx:1.27-alpine` | `80` | 统一入口：`/` 代理到前端，`/api/` 代理到 edge-backend。 |
| `gpu-tools` | `nvidia/cuda:12.6.3-base-ubuntu22.04` | 无对外端口 | 可选 Profile `gpu`，仅用于 GPU 验证，非主业务。 |

### 3.2 网络与访问路径

- **推荐浏览器入口**：`http://localhost`（经 nginx）。
- **直连调试**：
  - 前端：`http://localhost:3000`
  - 边缘后端：`http://localhost:8000`

### 3.3 Nginx 路由约定

- `GET /` 及静态资源请求 → `frontend:3000`
- `/api/` → `edge-backend:8000`（路径前缀在 nginx 中去掉后转发）

前端页面内若使用相对路径 `/api/...`，则与上述入口一致。

### 3.4 持久化

- `a22_logs`：容器内挂载为 `/logs`，用于运行日志（随实现演进）。
- `a22_data`：容器内挂载为 `/data`，用于本地缓存与临时数据。

---

## 4. 请求与数据流（当前阶段）

### 4.1 本地闭环（浏览器 → 边缘）

```text
浏览器 (Windows)
  -> http://localhost (nginx)
  -> frontend (页面)
  -> fetch /api/... (同源经 nginx)
  -> edge-backend
  -> 返回 JSON 给前端展示
```

### 4.2 与实验室服务器通信（SSH 隧道）

当远程 HTTP 服务仅监听 **远端本机**（例如 `127.0.0.1:19000`）时，在 **WSL 本地** 建立 SSH 本地端口转发：

```bash
ssh -N -L 127.0.0.1:19000:127.0.0.1:19000 <user>@<lab-host>
```

含义：

- 本地监听 `127.0.0.1:19000`
- 流量经 SSH 加密通道到远端 `127.0.0.1:19000`

边缘后端配置中，将远端基址指向隧道本地地址即可，例如：

- `CLOUD_API_BASE=http://127.0.0.1:19000`

这样 **应用层始终使用 HTTP 调用本地地址**，不直接绑定 SSH 细节，便于切换环境。

### 4.3 已验证的连通性

当前已验证：

- `GET /health` 经隧道可达。
- `POST /chat` 经隧道可达，且远端能收到请求并返回 JSON。

---

## 5. 消息与接口约定（v0 已落盘）

**v0** 正式定义见 `shared/contracts/api_v1.md`，示例见：

- `shared/contracts/chat_request.example.json`
- `shared/contracts/chat_response.example.json`

边缘与 orchestrator 实现应与此对齐；本文档不再重复字段表。

---

## 6. 远程侧（实验室）演进规划

当前远程侧可先用 **最小 HTTP 服务** 验证隧道与协议；后续按模块拆分，例如：

| 模块 | 职责 |
|------|------|
| `orchestrator` | 总调度、会话状态、聚合下游结果。 |
| `llm-service` | 大语言模型推理。 |
| `rag-service` | 心理知识库检索。 |
| `tts-service` | 语音合成（若云端生成）。 |
| `state-estimator` | 多模态或文本状态估计。 |
| 向量库 / 缓存 | 如 Qdrant、Redis 等（按部署选择）。 |

远程侧 **单独** 使用 `compose.remote.yaml`（或等价编排）管理，与本地 `compose.local.yaml` 分离，避免职责混用。

---

## 7. 延迟与传输（架构视角）

- **SSH 隧道**：在文本 JSON、小 payload 场景下，通常不是主要瓶颈；**隧道应常驻**，避免每轮业务请求都重新握手。
- **主要耗时**：往往来自远端推理与检索，而非本地到实验室的纯传输时间。
- **减小延迟与体积**的做法：会话上下文由远端维护；边缘每轮只发增量；返回只含前端展示所需字段；避免原始音视频全量直传（除非业务明确要求）。

---

## 8. 安全与认证（简述）

- **实验室登录**：当前可为账号密码；长期开发建议在本机生成密钥对，将公钥写入远端用户 `~/.ssh/authorized_keys`，便于稳定隧道与自动化。  
- **密钥与 sudo**：普通用户生成密钥、写入自己的 `authorized_keys` **一般不需要 sudo**；仅当服务器策略禁止或需改系统级 `sshd` 配置时才可能涉及管理员。

---

## 9. 仓库内文档关系

| 文件 | 内容 |
|------|------|
| `README.md` | 环境搭建、Compose 启动、复现步骤、GPU 验证命令。 |
| `ARCHITECTURE.md`（本文） | 系统分层、服务、数据流、SSH 隧道在架构中的位置、远程演进规划。 |
| `shared/contracts/api_v1.md` | 边缘与 orchestrator 的 HTTP JSON 契约（v0）。 |

---

## 10. 变更记录

- **初版**：记录 WSL2 + Docker Desktop 本地骨架、实验室 SSH 隧道 HTTP 验证路径及远程推理职责划分。
- **v0 结构**：`local/`、`remote/`、`shared/contracts/` 拆分；新增 `compose.remote.yaml` 与 `remote/orchestrator` 骨架。
