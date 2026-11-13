import json
from functools import lru_cache
from typing import Any

from api import settings
from api.models import CaseReference, LegalReference
from data.vector_db import ChromaVectorStore, LocalVectorStore, SearchHit


def _read_json(path):
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_legal_items() -> list[dict]:
    return _read_json(settings.LEGAL_KB_PATH)


@lru_cache(maxsize=1)
def load_case_items() -> list[dict]:
    return _read_json(settings.CASE_KB_PATH)


@lru_cache(maxsize=1)
def local_legal_store() -> LocalVectorStore:
    return LocalVectorStore(load_legal_items(), text_fields=["title", "article", "excerpt", "region"], keyword_field="keywords")


@lru_cache(maxsize=1)
def local_case_store() -> LocalVectorStore:
    return LocalVectorStore(load_case_items(), text_fields=["title", "summary", "region"], keyword_field="keywords")


@lru_cache(maxsize=1)
def chroma_legal_store() -> ChromaVectorStore:
    return ChromaVectorStore(settings.LAW_COLLECTION_NAME)


@lru_cache(maxsize=1)
def chroma_case_store() -> ChromaVectorStore:
    return ChromaVectorStore(settings.CASE_COLLECTION_NAME)


@lru_cache(maxsize=1)
def chroma_available() -> bool:
    if not settings.wants_chroma():
        return False
    try:
        return chroma_legal_store().count() > 0 or chroma_case_store().count() > 0
    except Exception:
        return False


@lru_cache(maxsize=1)
def active_backend_name() -> str:
    if settings.KNOWLEDGE_BACKEND == "local_json":
        return "local_json"
    if settings.KNOWLEDGE_BACKEND == "chromadb":
        return "chromadb"
    return "chromadb" if chroma_available() else "local_json"


def _normalize_legal_payload(payload: dict[str, Any], *, score: float, matched_tokens: list[str]) -> LegalReference:
    normalized = {
        "id": str(payload.get("id") or payload.get("chunk_id") or payload.get("source_doc_id") or "unknown-law"),
        "title": str(payload.get("title") or payload.get("law_name") or "未知法规"),
        "article": str(payload.get("article") or payload.get("article_no") or payload.get("article_id") or "未标注条款"),
        "excerpt": str(payload.get("excerpt") or payload.get("content_preview") or payload.get("document") or ""),
        "source_level": payload.get("source_level") or _infer_source_level(payload),
        "dispute_type": payload.get("dispute_type"),
        "region": payload.get("region") or payload.get("jurisdiction"),
        "keywords": list(payload.get("keywords") or []),
        "score": score,
        "matched_tokens": matched_tokens,
        "source_url": payload.get("source_url"),
        "effective_status": payload.get("effective_status"),
    }
    return LegalReference(**normalized)


def _normalize_case_payload(payload: dict[str, Any], *, score: float, matched_tokens: list[str]) -> CaseReference:
    normalized = {
        "id": str(payload.get("id") or payload.get("chunk_id") or payload.get("source_doc_id") or "unknown-case"),
        "title": str(payload.get("title") or "未知案例"),
        "summary": str(payload.get("summary") or payload.get("excerpt") or payload.get("document") or ""),
        "dispute_type": str(payload.get("dispute_type") or "一般民事纠纷"),
        "region": payload.get("region") or payload.get("jurisdiction"),
        "keywords": list(payload.get("keywords") or []),
        "handling_points": list(payload.get("handling_points") or []),
        "score": score,
        "matched_tokens": matched_tokens,
        "source_url": payload.get("source_url"),
    }
    return CaseReference(**normalized)


def _infer_source_level(payload: dict[str, Any]) -> str:
    law_type = str(payload.get("law_type") or "").lower()
    title = str(payload.get("title") or "")
    if "地方" in law_type or any(tag in title for tag in ["北京", "上海", "广东", "江苏", "浙江"]):
        return "local"
    return "national"


def _search_hits(store, *, query: str, dispute_type: str | None, region: str | None, limit: int) -> list[SearchHit]:
    return store.search(query=query, dispute_type=dispute_type, region=region, limit=limit)


def search_legal(*, dispute_type: str | None, query: str, region: str | None, limit: int) -> list[LegalReference]:
    backend = active_backend_name()
    store = chroma_legal_store() if backend == "chromadb" else local_legal_store()
    hits = _search_hits(store, query=query, dispute_type=dispute_type, region=region, limit=limit)
    return [_normalize_legal_payload(hit.payload, score=hit.score, matched_tokens=hit.matched_tokens) for hit in hits]


def search_cases(*, dispute_type: str | None, query: str, region: str | None, limit: int) -> list[CaseReference]:
    backend = active_backend_name()
    store = chroma_case_store() if backend == "chromadb" else local_case_store()
    hits = _search_hits(store, query=query, dispute_type=dispute_type, region=region, limit=limit)
    return [_normalize_case_payload(hit.payload, score=hit.score, matched_tokens=hit.matched_tokens) for hit in hits]


def knowledge_counts() -> dict[str, int]:
    backend = active_backend_name()
    if backend == "chromadb":
        try:
            return {
                "legal_items": chroma_legal_store().count(),
                "case_items": chroma_case_store().count(),
            }
        except Exception:
            pass
    return {
        "legal_items": len(load_legal_items()),
        "case_items": len(load_case_items()),
    }


def clear_caches() -> None:
    load_legal_items.cache_clear()
    load_case_items.cache_clear()
    local_legal_store.cache_clear()
    local_case_store.cache_clear()
    chroma_legal_store.cache_clear()
    chroma_case_store.cache_clear()
    chroma_available.cache_clear()
    active_backend_name.cache_clear()
