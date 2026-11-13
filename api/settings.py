"""全局配置模块。

所有运行时配置集中在此处，供 api/repositories/services/ingestion 复用。
敏感信息（API Key）一律经环境变量或 .env 读取，严禁硬编码。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（api/ 的上一级），并加载根目录 .env
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env", override=False)

# ---- 基础信息 ----
APP_NAME = "智慧调解助手 API"
APP_DESCRIPTION = "基层调解智能辅助系统"
APP_VERSION = "0.7.0"

# ---- 目录 ----
STORAGE_DIR = BASE_DIR / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# 向量数据库持久化目录：统一以 CHROMA_DIR 为准，兼容旧变量 CHROMA_PERSIST_DIR。
# 修复：此前各处硬编码 "./storage/chroma"，导致不同启动目录路径不一致（PROBLEMS P2）。
CHROMA_DIR = Path(
    os.getenv("CHROMA_DIR", os.getenv("CHROMA_PERSIST_DIR", str(STORAGE_DIR / "chroma")))
)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

# Chroma collection 名称（法规库 / 案例库分离）
LAW_COLLECTION_NAME = os.getenv("LAW_COLLECTION_NAME", "legal_knowledge_v1")
CASE_COLLECTION_NAME = os.getenv("CASE_COLLECTION_NAME", "case_knowledge_v1")

# ---- 本地知识库（JSON 回退，默认离线跑通的数据源）----
# 修复：补齐仓储层/建库脚本依赖但此前缺失的常量（PROBLEMS P2）。
LEGAL_KB_PATH = Path(os.getenv("LEGAL_KB_PATH", str(BASE_DIR / "data" / "legal_knowledge_base.json")))
CASE_KB_PATH = Path(os.getenv("CASE_KB_PATH", str(BASE_DIR / "data" / "case_knowledge_base.json")))

# ---- 建库参数与原始导出文件 ----
INGEST_CHUNK_SIZE = int(os.getenv("INGEST_CHUNK_SIZE", "500"))
INGEST_CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "50"))
LAW_SOURCE_EXPORT = Path(os.getenv("LAW_SOURCE_EXPORT", str(STORAGE_DIR / "raw" / "laws.jsonl")))
CASE_SOURCE_EXPORT = Path(os.getenv("CASE_SOURCE_EXPORT", str(STORAGE_DIR / "raw" / "cases.jsonl")))

# ---- 运行模式 ----
# 自动优先使用已有 Chroma collection；未建库时回退本地 JSON，无需联网下载模型。
KNOWLEDGE_BACKEND = os.getenv("KNOWLEDGE_BACKEND", "auto")  # auto/local_json/chromadb
VECTOR_BACKEND = os.getenv("VECTOR_BACKEND", "auto")  # auto/in_memory_weighted/chromadb
KNOWLEDGE_RETRIEVAL_MODE = os.getenv("KNOWLEDGE_RETRIEVAL_MODE", "dual_kb_retrieval")

# ---- Embedding 模型 ----
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
EMBEDDING_DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")

# ---- Ollama 生成配置 ----
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "45"))
GENERATION_PROVIDER = os.getenv("GENERATION_PROVIDER", "ollama")  # ollama/openai/aliyun/rule
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "qwen2:0.5b")

# ---- OpenAI 兼容配置（可选）----
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")

# ---- 阿里云百炼（DashScope）OpenAI 兼容配置（可选）----
# 补充 aliyun_llm_key 调用方式（agent_role 目标）。Key 仅经环境变量/.env 读取。
ALIYUN_LLM_KEY = os.getenv("ALIYUN_LLM_KEY", "")
ALIYUN_BASE_URL = os.getenv("ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
ALIYUN_MODEL = os.getenv("ALIYUN_MODEL", "qwen-plus")

# ---- 功能开关 ----
# 默认关闭 LLM/RAG，保证未配置模型时也能以规则拼装稳定演示；按需开启。
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
RAG_ENABLED = os.getenv("RAG_ENABLED", "false").lower() == "true"

# ---- CORS 允许的前端地址 ----
DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


def get_allowed_origins() -> list[str]:
    """解析 CORS_ORIGINS 环境变量，缺省回退到本地前端地址。"""
    raw = os.getenv("CORS_ORIGINS", "")
    origins = [item.strip() for item in raw.split(",") if item.strip()]
    return origins or DEFAULT_CORS_ORIGINS


def has_openai_credentials() -> bool:
    """是否已配置 OpenAI 兼容密钥。"""
    return bool(OPENAI_API_KEY)


def has_aliyun_credentials() -> bool:
    """是否已配置阿里云百炼密钥。"""
    return bool(ALIYUN_LLM_KEY)


def wants_chroma() -> bool:
    """当前配置是否期望使用 Chroma 向量库。"""
    return KNOWLEDGE_BACKEND in {"auto", "chromadb"} or VECTOR_BACKEND in {"auto", "chromadb"}


def llm_generation_enabled() -> bool:
    """判断 LLM 生成链路是否可用（开关 + provider 凭证）。"""
    if not (LLM_ENABLED and RAG_ENABLED and bool(GENERATION_MODEL)):
        return False
    if GENERATION_PROVIDER == "ollama":
        return bool(OLLAMA_BASE_URL)
    if GENERATION_PROVIDER == "openai":
        return has_openai_credentials()
    if GENERATION_PROVIDER == "aliyun":
        return has_aliyun_credentials()
    return False