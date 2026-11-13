# 智慧调解助手（V7：合并双库 RAG · 离线可跑通版）

基层调解智能辅助系统。本版本在 V6 基础上**只做删改/合并**：将两套并行 RAG 框架合并为唯一主链路，
修复配置/接口不一致，补齐阿里云百炼（aliyun）密钥调用方式，并保证**未下载模型、未启动 Chroma 时也能离线演示**。

## 核心变化（相对 V6）

- **合并为唯一 RAG 主链路**：保留 `repositories/` + `services/` 双知识库（法规库 + 案例库）框架，
  删除旧 `rag/` 单库引擎（`engine/retriever/generator/prompts`）。
- **默认离线跑通**：`KNOWLEDGE_BACKEND=local_json`、`VECTOR_BACKEND=in_memory_weighted`、
  `LLM_ENABLED=false`、`RAG_ENABLED=false`。无需下载 embedding 模型或启动 Ollama，即可用本地 JSON + 规则拼装演示。
- **三种生成 provider**：`ollama`（默认 `qwen2:0.5b`）/ `openai`（兼容端点）/ `aliyun`（DashScope OpenAI 兼容）。
  密钥仅经环境变量 / `.env` 读取，严禁硬编码。
- **可选真实向量检索**：将后端切到 `auto`/`chromadb` 并建库后，使用 Chroma + `BAAI/bge-small-zh-v1.5` 语义检索。
- **前端结构化渲染 + 错误态**：`WorkspacePage` 复用 `ResultPanel` 展示摘要/法规/案例/步骤/情绪/运行模式，
  请求失败在页面显示原因（不再仅打印到 console）。

## 目录说明

- `api/`：接口层（`main.py` 入口、`routes.py` 路由）与全局配置（`settings.py`）
- `core/`：纠纷识别、情绪引导、决策支持（规则回退）
- `repositories/`：双知识库访问层（`knowledge_repository.py`）
- `services/`：编排层（`mediation_service`）、检索（`legal_kb_service`）、生成（`llm_generation_service`）、建库（`ingest_service`）
- `data/`：向量层适配器（`vector_db.py`）与本地 seed 知识库 JSON
- `ingestion/`：离线建库脚本（`build_chroma_db.py`）
- `storage/`：Chroma 持久化目录（`chroma/`，已忽略）与可选原始导入目录（`raw/`）
- `frontend/`：React + Vite + TypeScript 前端
- `tests/`：pytest 单元测试（`test_unit.py`）与离线冒烟（`mock_test.py`）

## 后端启动

### Windows PowerShell

```powershell
cd wisdom_mediator
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python tests/mock_test.py
python -m uvicorn api.main:app --reload --port 8000
```

### macOS / Linux

```bash
cd wisdom_mediator
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
python tests/mock_test.py
python -m uvicorn api.main:app --reload --port 8000
```

启动成功后访问：

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

> 默认 `.env`（由 `.env.example` 复制）关闭 LLM/RAG。知识后端会优先使用已建好的 Chroma
> collection；未建库时回退到 local_json。只有执行向量检索或建库时才需要加载本地 embedding 模型。
> 规则生成不依赖在线大模型服务。

## 前端启动

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

默认前端地址：`http://localhost:5173`

开发环境默认通过 Vite 的 `/api` 代理连接 `http://127.0.0.1:8000`，无需依赖前后端端口相同。

## 测试

```bash
# 冒烟（自动选择可用知识库，无需在线 LLM；Chroma 检索需要本地 embedding 缓存）
python tests/mock_test.py

# 单元测试（配置/向量适配器契约/仓储归一化/LLM JSON 解析/规则回退 + 边缘）
python -m pytest tests/test_unit.py -q
```

## 生成模型配置（三选一）

`.env.example` 默认（离线规则拼装，不调用大模型）：

```env
KNOWLEDGE_BACKEND=local_json
VECTOR_BACKEND=in_memory_weighted
GENERATION_PROVIDER=ollama
GENERATION_MODEL=qwen2:0.5b
LLM_ENABLED=false
RAG_ENABLED=false
```

如需启用大模型生成，打开开关并按 provider 配置：

```env
LLM_ENABLED=true
RAG_ENABLED=true
```

### 1. Ollama（本地）

```env
GENERATION_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
GENERATION_MODEL=qwen2:0.5b   # 换成你本地实际标签，如 qwen3:8b
```

### 2. OpenAI 兼容端点

```env
GENERATION_PROVIDER=openai
OPENAI_API_KEY=sk-xxxx
OPENAI_BASE_URL=https://api.openai.com/v1
GENERATION_MODEL=gpt-4o-mini
```

### 3. 阿里云百炼（DashScope，OpenAI 兼容）

```env
GENERATION_PROVIDER=aliyun
ALIYUN_LLM_KEY=sk-xxxx
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ALIYUN_MODEL=qwen3.8-27b
```

> 密钥只放在 `.env` 或环境变量中，切勿提交到仓库。

## 可选：真实向量检索（Chroma + BGE）

### 1. Embedding 模型

```env
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
```

### 2. 切换后端并建库

```env
KNOWLEDGE_BACKEND=auto
VECTOR_BACKEND=auto
CHROMA_DIR=./storage/chroma
LAW_COLLECTION_NAME=legal_knowledge_v1
CASE_COLLECTION_NAME=case_knowledge_v1
```

准备法规/案例导出文件（JSON 或 JSONL），放到 `storage/raw/laws.jsonl`、`storage/raw/cases.jsonl`。
字段建议：

- 法规：`id`、`title`、`article`、`content`、`region`、`dispute_type`、`keywords`、`source_url`、`effective_status`
- 案例：`id`、`title`、`summary`、`content`、`region`、`dispute_type`、`keywords`、`handling_points`、`source_url`

建库（二选一）：

```bash
python ingestion/build_chroma_db.py --rebuild
```

如果报错ModuleNotFoundError，改为：python -m ingestion.build_chroma_db --rebuild
```http
POST /system/build-real-kb
```

建库完成后，系统优先使用 `chromadb` 语义检索；不可用时自动回退 local_json。

## 运行逻辑（唯一主链路）

1. 用户提交案件描述到 `/mediate`（或 `/mediation/generate`）。
2. `services/mediation_service` 完成纠纷识别与情绪识别。
3. `services/legal_kb_service.search_dual_knowledge` 从法规库 + 案例库检索（默认 local_json，可选 Chroma）。
4. 若 `llm_generation_enabled()` 为真，`services/llm_generation_service.generate_with_llm`
   基于检索证据做结构化生成（ollama/openai/aliyun）；失败自动回退 `core/decision_support` 规则拼装。
5. 返回摘要、法规依据、案例参考、调解步骤、情绪引导与运行态（`runtime`）。

## 主要接口

- `GET /health`：真实运行态（知识库是否加载、法规/案例计数、检索模式）
- `GET /system/runtime-profile`：运行态 + 知识计数
- `POST /mediate`、`POST /mediation/generate`：调解主链路
- `POST /knowledge/search`：双库检索（支持 `dispute_type`/`region` 过滤）
- `POST /system/build-real-kb`：离线建库
- `GET /cases`、`GET /mock/cases`、`GET /mock/mediation/{id}`：演示数据

## 交接

下一位开发者请先读 `Read_Before_you_takeover.md`（架构、启动、env 键、已知限制），
改进进度与错误总结见 `PROJECT_PLAN.md`。