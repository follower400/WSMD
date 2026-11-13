# 交接文档 · 智慧调解助手 V7（合并双库 RAG）

> 面向下一位开发者。本轮改进**只删改/合并、不新增功能**，目标是把两套并行 RAG 框架合并为唯一主链路、
> 修复配置/接口不一致、补齐 aliyun 密钥调用方式，并保证离线最小跑通。

## 1. 一句话现状

- 默认 **local_json + in_memory_weighted + 规则拼装**，`LLM_ENABLED=false`、`RAG_ENABLED=false`：
  不下载模型、不启动 Chroma/Ollama 即可 `python tests/mock_test.py` 与 `/mediate` 离线演示。
- 唯一 RAG 主链路：`repositories/`（双库）+ `services/`（编排/检索/生成/建库）。旧 `rag/` 已删除。
- 生成 provider 三选一：`ollama` / `openai` / `aliyun`（DashScope OpenAI 兼容）。密钥仅经 `.env`/环境变量。

## 2. 合并后架构（唯一链路）

```
POST /mediate, /mediation/generate
  └ services/mediation_service.generate_mediation
      ├ core.dispute_recognition / core.emotion_guidance      # 纠纷 + 情绪识别
      ├ services.legal_kb_service.search_dual_knowledge        # repositories 双库检索
      │    └ repositories/knowledge_repository.py              # local_json / chromadb 适配
      │         └ data/vector_db.py                            # LocalVectorStore / ChromaVectorStore / SearchHit
      ├ services.llm_generation_service.generate_with_llm      # ollama/openai/aliyun，结构化 JSON
      │    └ 失败回退 core.decision_support.build_summary/build_steps
      └ services.legal_kb_service.get_runtime_profile          # 运行态
```

- 向量层 `data/vector_db.py`：
  - `SearchHit(text, metadata, score, payload, matched_tokens)`——仓储读取 `payload/matched_tokens/score`。
  - `LocalVectorStore(items, *, text_fields, keyword_field)`：jieba 关键词打分 + `dispute_type/region` 过滤
    （`region` 为 `None`/`全国` 视为普适）。默认后端，离线可用。
  - `ChromaVectorStore(collection_name, embedder=None)`：懒加载 `_ensure_db()`，`search(query,*,dispute_type,region,limit)`、
    `count()`、`is_available()`、`add_documents()`、`clear()`；路径统一 `settings.CHROMA_DIR`。
  - `LegalVectorDB`：底层 chroma + embedding，**懒加载**，local_json 默认不触发模型下载。

## 3. 关键文件

| 文件 | 职责 |
| --- | --- |
| `api/settings.py` | 全局配置；所有常量/路径/开关/provider 凭证集中于此 |
| `api/main.py` | 纯入口（app + router + CORS + 根重定向）；**不再** eager 初始化向量库 |
| `api/routes.py` | 单一真实 `/health`、`/system/runtime-profile`、`/knowledge/search`、`/system/build-real-kb` 等 |
| `services/mediation_service.py` | 主链路编排：双库检索 + 结构化生成 + 规则回退 |
| `services/legal_kb_service.py` | `search_dual_knowledge` / `get_runtime_profile` / `knowledge_counts` |
| `services/llm_generation_service.py` | `generate_with_llm`；`_generate_with_aliyun`；JSON 解析 |
| `repositories/knowledge_repository.py` | 双库访问、`_normalize_*`、`active_backend_name` |
| `data/vector_db.py` | 向量适配器（见上） |
| `ingestion/build_chroma_db.py` | 离线建库 CLI（`build_documents/read_records/load_fallback_records`） |
| `frontend/src/pages/WorkspacePage.tsx` | 复用 `ResultPanel` 结构化渲染 + 页面错误态 |

## 4. 启动与测试

```bash
# 后端（离线默认）
python -m pip install -r requirements.txt
cp .env.example .env            # Windows: Copy-Item .env.example .env
python tests/mock_test.py       # 离线冒烟，应 EXIT=0
python -m pytest tests/test_unit.py -q   # 单元测试（19 用例）
python -m uvicorn api.main:app --reload --port 8000

# 前端
cd frontend && cp .env.example .env && npm install && npm run dev
```

- 冒烟校验点：`/health` 计数（默认 6 法规 / 3 案例）、`/mediate` 识别“邻里纠纷”含 legal_basis + case_references + steps + emotion、
  `/knowledge/search` 带过滤、404/422 校验。
- 前端 `npm run build`（tsc + vite）应通过。

## 5. 环境变量键（`.env.example` 已对齐）

- 运行模式：`KNOWLEDGE_BACKEND`(local_json/auto/chromadb)、`VECTOR_BACKEND`(in_memory_weighted/auto/chromadb)、`KNOWLEDGE_RETRIEVAL_MODE`
- 向量库：`CHROMA_DIR`（兼容旧 `CHROMA_PERSIST_DIR`）、`LAW_COLLECTION_NAME`、`CASE_COLLECTION_NAME`、`INGEST_CHUNK_SIZE`、`INGEST_CHUNK_OVERLAP`
- 本地库：`LEGAL_KB_PATH`、`CASE_KB_PATH`
- 生成：`GENERATION_PROVIDER`(ollama/openai/aliyun)、`GENERATION_MODEL`、`LLM_ENABLED`、`RAG_ENABLED`
- Ollama：`OLLAMA_BASE_URL`、`OLLAMA_TIMEOUT`
- OpenAI：`OPENAI_API_KEY`、`OPENAI_BASE_URL`
- **阿里云（本轮新增）**：`ALIYUN_LLM_KEY`、`ALIYUN_BASE_URL`(默认 DashScope 兼容端点)、`ALIYUN_MODEL`(默认 qwen3.8-27b)
- Embedding：`EMBEDDING_PROVIDER`、`EMBEDDING_MODEL`(BAAI/bge-small-zh-v1.5)、`EMBEDDING_DEVICE`
- 导出：`LAW_SOURCE_EXPORT`、`CASE_SOURCE_EXPORT`
- CORS：`CORS_ORIGINS`

> 启用大模型：`LLM_ENABLED=true` + `RAG_ENABLED=true`，再按 provider 配好端点/密钥。
> 启用真实检索：`KNOWLEDGE_BACKEND=auto` + `VECTOR_BACKEND=auto`，建库后生效。**密钥切勿提交仓库。**

## 6. 如何启用真实链路（可选）

1. 准备 `storage/raw/laws.jsonl`、`storage/raw/cases.jsonl`（字段见 README）。
2. `python ingestion/build_chroma_db.py --rebuild` 或 `POST /system/build-real-kb`。
3. `.env` 切 `auto`/`chromadb`，配好 Ollama/OpenAI/aliyun 之一并打开 LLM/RAG 开关。
4. 复测 `/mediate`：`runtime.generation_mode` 应为 `rag_llm`，`source=live`。

## 7. 已知限制 / 待办（交给下一位）

- **P9 · storage/chroma 跟踪混杂**：`storage/chroma/chroma.sqlite3` 曾被 Git 跟踪（现 `.gitignore` 已忽略 `storage/chroma/` 与 `*.sqlite3`，
  但历史提交仍含该二进制）。推到新仓库前建议 `git rm --cached` 取消跟踪，避免二进制入库。**取消跟踪属破坏性操作，需先请示。**
- **浏览器交互未实测**：本轮环境无浏览器工具，前端仅通过 `npm run build` + 后端 `/health`/index 200 验证；
  未做交互式点击（主路径 + 错误路径）。下一位请在浏览器实测提交案例与后端失败提示。
- **Chroma 语义检索为可选增强**：默认 local_json 关键词打分；真实向量检索需自行建库并下载 embedding 模型。
- **旧 `rag/` 已删除**：如需回溯，见备份分支 `backup/pre-merge`（指向合并前 HEAD）。
- 默认生成模型 `qwen2:0.5b` 仅为占位，请按本地 Ollama 实际标签或云端模型替换。

## 8. 约束（coderrules）

- 只删改/合并，不新增功能；单文件模块优先；中文注释；密钥经环境变量/`.env`；脚本引用根模块显式 `sys.path`。
- 核心逻辑单元测试 + 主链路冒烟 + 边缘覆盖（空查询/无命中、缺失字段、空知识库）。
- 数据安全：默认 local_json 离线跑通；破坏性 git / 取消跟踪先请示。
