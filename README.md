# A22 本地开发骨架

## 1. 项目目标
本项目面向 A22 情感陪护虚拟数字人系统。

当前阶段的目标是在保持本地展示与转发链路稳定的前提下，完成远端真实推理服务接入与联调，包括：

- 前端展示界面
- 本地边缘后端
- 本地统一入口
- 与远程真实推理服务的接口对接

## 2. 当前系统架构
当前架构按三层划分：

1. Windows 层  
   用于开发入口和展示入口，包括 `VS Code / Cursor`、浏览器、`Docker Desktop`。

2. WSL2 Ubuntu 22.04 层  
   作为本地 Linux 开发与运行环境，承载项目源码、本地 `frontend`、本地 `edge-backend`、`nginx`、日志与缓存。

3. Remote Server 层  
   承载全部推理相关服务，包括 `LLM`、`RAG`、`TTS`、多模态融合、状态评估等。

当前约定是：**所有正式推理全部部署在远程服务器，本地 WSL 仅负责展示、业务处理、转发和接口预留。**

## 3. 技术栈
当前本地开发骨架使用如下技术栈：

- Windows 11 + WSL2
- Ubuntu 22.04
- Docker Desktop
- Docker Compose
- Nginx
- Node.js 20
- Vite
- Python 3.11
- FastAPI
- NVIDIA GPU through WSL2 + Docker Desktop

## 4. 本地 Compose 服务说明
当前本地 `docker compose` 管理以下服务：

- `frontend`  
  本地前端开发服务与页面渲染入口。

- `edge-backend`  
  本地边缘后端，负责会话管理、请求处理、转发预留和 mock 返回。

- `nginx`  
  本地统一入口，用于路由前端页面和 `/api` 请求。

- `gpu-tools`  
  可选 GPU 工具容器，仅用于验证本机 GPU 到容器的链路，不属于主业务容器。

## 5. 目录结构
```text
A22/
├─ compose.yaml
├─ compose.local.yaml
├─ compose.remote.yaml
├─ README.md
├─ ARCHITECTURE.md
├─ System_Design/
│  ├─ version1/
│  └─ version2/
├─ local/
│  ├─ frontend/
│  ├─ edge-backend/
│  └─ README.md
├─ remote/
│  ├─ orchestrator/
│  └─ qwen-server/
├─ shared/
│  ├─ contracts/
│  └─ README.md
├─ infra/nginx/
├─ logs/
└─ data/
```

## 6. Docker 在 WSL 下的配置步骤
本项目采用 **Windows 侧 Docker Desktop + WSL2 Ubuntu 22.04** 的方式，不在 WSL 内额外安装独立的 Docker Engine。

### 6.1 Windows 侧准备
1. 安装并更新 `WSL2`
2. 安装 `Docker Desktop`
3. 安装支持 WSL 的 `NVIDIA` 显卡驱动

### 6.2 Docker Desktop 设置
在 `Docker Desktop` 中确认：

- `Use WSL 2 based engine` 已开启
- `Resources > WSL Integration` 中已启用默认发行版
- `Ubuntu-22.04` 已勾选集成

### 6.3 WSL 内验证 Docker
进入 `Ubuntu-22.04` 后执行：

```bash
docker version
docker compose version
docker context ls
```

### 6.4 GPU 通路验证
当前环境已验证可用的测试镜像为：

```bash
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
```

如果容器中可以正常显示本机显卡信息，说明 `WSL2 + Docker Desktop + GPU` 链路可用。

## 7. 首次拉起项目的操作步骤
如果是首次在当前机器拉起本项目，建议按下面步骤执行。

### 7.1 进入项目目录
```bash
cd ~/docker_ws/A22
```

### 7.2 拉取基础镜像
```bash
docker pull node:20-bookworm-slim
docker pull python:3.11-slim-bookworm
docker pull nginx:1.27-alpine
docker pull nvidia/cuda:12.6.3-base-ubuntu22.04
docker pull nvidia/cuda:12.6.3-cudnn-runtime-ubuntu22.04
```

### 7.3 启动本地服务
```bash
docker compose -f compose.yaml -f compose.local.yaml up -d
```

### 7.4 查看运行状态
```bash
docker compose -f compose.yaml -f compose.local.yaml ps
```

### 7.5 查看日志
```bash
docker compose -f compose.yaml -f compose.local.yaml logs -f
```

### 7.6 远端 server 推理与 orchestrator（实验室服务器）

当前远端代码目录位于：

```bash
/home/zifeng/siyuan/A22/A22_wmzjbyGroup
```

当前模型目录位于：

```bash
/data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct
```

当前推荐采用两层服务：

- `remote/qwen-server`：独立运行 `vLLM`，提供 OpenAI-compatible HTTP 接口
- `remote/orchestrator`：维持 `/chat` 契约与结构化返回，内部调用 `qwen-server`

注意：

- 模型权重必须放在 `/data/...`，不要放到 `/home`
- `uv` 虚拟环境可以放在项目目录，即 `/home/...` 下
- `remote/orchestrator/.venv` 如果已经存在，不需要重建；只有在依赖新增或 `pyproject.toml` 更新后，再执行一次同步安装即可
- `remote/qwen-server/.venv` 建议独立创建，不要与 `orchestrator` 共用

#### 7.6.1 准备 qwen-server 的 `uv` 环境

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote
mkdir -p qwen-server
cd qwen-server
uv venv --python /usr/bin/python3.11 .venv
source .venv/bin/activate
uv pip install --upgrade pip
uv pip install vllm
```

兼容性说明：

- `vllm` 会自动安装其依赖的 `torch`、CUDA 相关 wheel 与运行时依赖
- 如果服务器驱动版本、Python 版本或 Linux 环境与 wheel 不匹配，安装阶段或启动阶段可能出现兼容问题
- 当前服务器为 `3 x RTX 4090 24GB`，运行 `Qwen2.5-7B-Instruct` 资源上是足够的，通常先按单卡部署即可
- 建议在全新独立 `.venv` 中安装 `vllm`，避免与其他推理框架依赖冲突
- 如果安装或启动异常，优先检查 `nvidia-smi`、Python 版本以及 `vllm` 安装日志

#### 7.6.2 启动 Qwen 模型服务

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
source .venv/bin/activate
export CUDA_VISIBLE_DEVICES=<cuda_id>
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

启动后可在服务器本机验证：

```bash
curl http://127.0.0.1:8000/v1/models
```

其中：

- `<cuda_id>` 可以填 `0`、`1` 或 `2`
- 单卡部署时，`CUDA_VISIBLE_DEVICES=1` 表示只让 vLLM 使用物理 1 号 GPU
- 当前 `Qwen2.5-7B-Instruct` 默认按单卡启动即可，不需要额外加 `tensor-parallel-size`

#### 7.6.3 准备 orchestrator 的 `uv` 环境

如果 `remote/orchestrator/.venv` 已经存在，直接复用即可：

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
source .venv/bin/activate
uv sync
```

如果 `.venv` 尚未创建，再执行：

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
uv venv --python /usr/bin/python3.11 .venv
source .venv/bin/activate
uv sync
```

当接入真实 Qwen provider 后，启动前需要设置：

```bash
export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
```

#### 7.6.4 启动 orchestrator 服务

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
source .venv/bin/activate
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

启动后可在服务器本机验证：

```bash
curl http://127.0.0.1:19000/health
```

说明：

- `local/edge-backend` 访问的是 `remote/orchestrator`
- `remote/orchestrator` 再向 `qwen-server` 发起模型调用
- 因此全链路运行时，服务器上必须同时启动 `qwen-server` 和 `orchestrator`

HTTP 契约见 `shared/contracts/api_v1.md`，远端详细说明见 `remote/orchestrator/README.md`。

### 7.7 当前版本全链路运行指令

当前版本完整链路不是 3 步，而是 4 步：

1. WSL 侧启动本地 Docker 服务
2. 服务器侧启动 `qwen-server`
3. 服务器侧启动 `orchestrator`
4. WSL 侧建立 SSH 隧道

#### 7.7.1 WSL 侧启动本地服务

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup
docker compose -f compose.yaml -f compose.local.yaml up -d
```

#### 7.7.2 服务器侧启动模型服务

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/qwen-server
source .venv/bin/activate
export CUDA_VISIBLE_DEVICES=<cuda_id>
python -m vllm.entrypoints.openai.api_server \
  --host 127.0.0.1 \
  --port 8000 \
  --model /data/zifeng/siyuan/A22/models/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --dtype auto \
  --gpu-memory-utilization 0.90 \
  --trust-remote-code
```

#### 7.7.3 服务器侧启动 orchestrator

```bash
cd /home/zifeng/siyuan/A22/A22_wmzjbyGroup/remote/orchestrator
source .venv/bin/activate
export LLM_PROVIDER=qwen
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_BASE=http://127.0.0.1:8000/v1
export LLM_API_KEY=EMPTY
export LLM_REQUEST_TIMEOUT_SECONDS=60
uv run uvicorn app:app --host 127.0.0.1 --port 19000
```

#### 7.7.4 WSL 侧建立 SSH 隧道

```bash
ssh -N -L 19000:127.0.0.1:19000 <server_user>@<server_host>
```

其中：

- 本地 `19000` 映射到远端 `orchestrator` 的 `19000`
- 本地应用继续通过 `CLOUD_API_BASE=http://127.0.0.1:19000` 访问远端服务

#### 7.7.5 全链路验证

WSL 侧验证远端链路：

```bash
curl http://127.0.0.1:19000/health
curl -X POST http://127.0.0.1:19000/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"hello","input_type":"text"}'
```

然后通过浏览器访问：

```bash
http://localhost
```

## 8. 已有 yml 情况下的复现步骤
如果仓库中已经存在 `compose.yaml` 和 `compose.local.yaml`，其他开发者复现本地环境时只需要完成以下操作。

### 8.1 前置条件
需要提前具备：

- Windows + WSL2
- Ubuntu 22.04
- Docker Desktop
- 已开启 WSL Integration

### 8.2 克隆仓库
```bash
git clone https://github.com/woruqingshan/A22_womenzhongjiangbaoyanGroup.git
cd A22_womenzhongjiangbaoyanGroup
```

如果你希望工作区仍位于 WSL 的 Linux 文件系统中，也可以先进入目标目录再克隆。

### 8.3 拉取依赖镜像
```bash
docker pull node:20-bookworm-slim
docker pull python:3.11-slim-bookworm
docker pull nginx:1.27-alpine
```

如果需要验证 GPU，再执行：

```bash
docker pull nvidia/cuda:12.6.3-base-ubuntu22.04
docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu22.04 nvidia-smi
```

### 8.4 启动服务
```bash
docker compose -f compose.yaml -f compose.local.yaml up -d
```

### 8.5 验证服务
```bash
docker compose -f compose.yaml -f compose.local.yaml ps
curl http://localhost:8000/health
curl -X POST http://localhost/api/chat -H "Content-Type: application/json" \
  -d '{"session_id":"demo-001","turn_id":1,"user_text":"hello","input_type":"text"}'
```

### 8.6 浏览器访问
推荐访问统一入口：

- `http://localhost`

补充说明：

- `http://localhost:3000` 是前端开发服务入口
- `http://localhost:8000` 是本地后端服务入口
- 当前完整链路推荐通过 `nginx` 的 `http://localhost` 来访问

## 9. 当前已完成内容
当前版本已经完成以下验证：

- `frontend` 容器已启动
- `edge-backend` 容器已启动
- `nginx` 容器已启动
- `http://localhost:8000/health` 可访问
- `http://localhost/api/chat` 可访问
- `docker compose` 已可作为本地多服务管理入口
- 远端 `remote/orchestrator` 已可通过 `uv` 运行
- 远端 `qwen-server` 已可作为独立模型服务部署
- SSH 隧道下的 `http://127.0.0.1:19000/health` 可访问
- SSH 隧道下的 `http://127.0.0.1:19000/chat` 可访问

补充说明：

- 当前已经完成“本地到远端 orchestrator”的通信验证
- 当前远端推理采用“`orchestrator -> qwen-server`”两层结构
- 当前目标是在不破坏 `/chat` 契约的前提下，将真实 Qwen provider 接入 `remote/orchestrator`

## 10. 下一步开发方向
下一阶段将基于当前骨架继续补齐以下功能：

- 将 `local/edge-backend` 改成真实调用 `CLOUD_API_BASE`
- 前端渲染界面优化与聊天区域设计
- 前端输入信号接入与消息状态管理
- 消息格式、发送接收接口与边缘侧数据处理
- 数字人形象控制与接收消息后的动作驱动逻辑
- 完成 `remote/orchestrator` 中 Qwen provider 的真实接入
- 保持 `/chat` 返回结构与现有 local/remote 协议兼容
