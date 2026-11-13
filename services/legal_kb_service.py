from api import settings
from api.models import CaseReference, LegalReference, RuntimeProfile
from repositories.knowledge_repository import (
    active_backend_name,
    chroma_available,
    chroma_case_store,
    chroma_legal_store,
    knowledge_counts,
    search_cases,
    search_legal,
)


def search_dual_knowledge(
    *,
    dispute_type: str | None,
    query: str,
    region: str | None,
    legal_limit: int = 5,
    case_limit: int = 3,
) -> tuple[list[LegalReference], list[CaseReference]]:
    legal_items = search_legal(
        dispute_type=dispute_type,
        query=query,
        region=region,
        limit=legal_limit,
    )
    case_items = search_cases(
        dispute_type=dispute_type,
        query=query,
        region=region,
        limit=case_limit,
    )
    return legal_items, case_items


def has_knowledge_bases() -> bool:
    counts = knowledge_counts()
    return counts["legal_items"] > 0 and counts["case_items"] > 0


def _detect_database_connected(backend: str) -> bool:
    if backend != "chromadb":
        return False
    try:
        if not chroma_available():
            return False
        return chroma_legal_store().is_available() or chroma_case_store().is_available()
    except Exception:
        return False


def _build_notes(
    *,
    backend: str,
    rag_enabled: bool,
    database_connected: bool,
) -> list[str]:
    notes: list[str] = []

    if backend == "chromadb":
        if database_connected:
            notes.append("当前版本已接入 Chroma 真实向量数据库，法规库与案例库分别存储到独立 collection。")
            notes.append("查询时先做纠纷识别与地域过滤，再执行双知识库检索。")
        else:
            notes.append("当前配置期望使用 Chroma，但数据库未连通或 collection 为空，运行时将回退到本地知识库。")
    else:
        notes.append("当前未使用 Chroma，运行时采用本地知识库或规则检索回退。")

    if rag_enabled:
        if settings.GENERATION_PROVIDER == "ollama":
            notes.append(f"已启用基于 Ollama 的证据约束生成，当前生成模型为 {settings.GENERATION_MODEL}。")
        elif settings.GENERATION_PROVIDER == "openai":
            notes.append("已启用基于 OpenAI 兼容接口的证据约束生成。")
        else:
            notes.append("已启用生成链路，但当前 provider 未知，请检查环境变量配置。")
    else:
        notes.append("当前未启用大模型生成，已回退到规则拼装结果。")

    if settings.EMBEDDING_MODEL:
        notes.append(f"当前 embedding 模型配置为 {settings.EMBEDDING_MODEL}。")

    return notes


def get_runtime_profile() -> RuntimeProfile:
    backend = active_backend_name()
    database_connected = _detect_database_connected(backend)
    supports_true_vector_search = backend == "chromadb" and database_connected

    rag_enabled = settings.llm_generation_enabled()
    generation_model = settings.GENERATION_MODEL if rag_enabled else None
    generation_mode = "rag_llm" if rag_enabled else "rule_based"

    return RuntimeProfile(
        knowledge_backend=backend,
        vector_backend="chromadb" if supports_true_vector_search else "in_memory_weighted",
        retrieval_mode=settings.KNOWLEDGE_RETRIEVAL_MODE,
        database_connected=database_connected,
        supports_true_vector_search=supports_true_vector_search,
        supports_rag_generation=rag_enabled,
        generation_model=generation_model,
        embedding_model=settings.EMBEDDING_MODEL,
        generation_mode=generation_mode,
        notes=_build_notes(
            backend=backend,
            rag_enabled=rag_enabled,
            database_connected=database_connected,
        ),
    )
