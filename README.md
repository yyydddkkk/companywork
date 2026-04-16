# Issue Multi-Agent MVP

一个用于 Issue 分析的全栈 MVP：
- 后端：FastAPI + LangGraph 编排（Triager / Researcher / Debugger / Documenter）
- 前端：React + Vite
- 数据：SQLite

## 1. 目录结构

- `backend/`：后端服务与测试
- `frontend/`：前端页面
- `data/`：本地数据库文件
- `.env.example`：环境变量模板

## 2. 快速启动

### 2.1 准备环境变量

在仓库根目录创建 `.env`（可从 `.env.example` 复制）：

```bash
cp .env.example .env
```

关键变量：
- `ENABLE_GITHUB_FETCH`：是否允许从 GitHub API 拉取 issue（`true/false`）
- `LLM_ENABLED`：是否启用 LLM
- `DEBUGGER_REQUIRE_LLM`：Debugger 失败时是否强制人工介入

### 2.2 启动后端

```bash
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

健康检查：

```bash
curl http://127.0.0.1:8001/health
```

### 2.3 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认前端会请求 `VITE_API_BASE` 指定的后端地址。

## 3. 常用接口

- `POST /api/issues/analyze`
- `POST /api/issues/analyze/upload`
- `GET /api/jobs/{job_id}`
- `GET /api/reports/{report_id}`
- `POST /api/reports/{report_id}/human-feedback`
- `POST /api/reports/{report_id}/rerun-debugger`

## 4. GitHub 连接超时排查（重点）

如果你看到类似错误：
- `httpx.ConnectTimeout`
- `/api/issues/analyze` 返回 500
- 堆栈落在 `issue_loader.py` 的 GitHub 拉取逻辑

通常不是业务逻辑问题，而是**网络路径或代理差异**。

### 4.1 典型现象

- 浏览器能打开 GitHub
- `curl -x "" https://www.github.com` 能通
- 但默认 `curl https://www.github.com` 或后端 `httpx` 超时

这说明：**直连可用，但默认代理链路不可用**（或代理策略拦截 GitHub）。

### 4.2 建议检查

```bash
env | grep -i proxy
curl -I --connect-timeout 5 https://www.github.com
curl -x "" -I --connect-timeout 5 https://www.github.com
```

- 若 `-x ""` 能通、默认不通：优先检查代理配置
- 若都不通：检查本机网络/DNS/防火墙

### 4.3 临时规避方案

- 不依赖 GitHub 拉取：`ENABLE_GITHUB_FETCH=false`
- 或启动后端时清空代理变量（按需）：

```bash
HTTP_PROXY= HTTPS_PROXY= ALL_PROXY= uv run uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## 5. 测试

```bash
cd backend
.venv/bin/python -m pytest -q
```

## 6. 安全提示

- 不要将真实 `GITHUB_TOKEN` / `LLM_API_KEY` 提交到仓库。
- 建议使用本地 `.env` 或密钥管理服务注入。
