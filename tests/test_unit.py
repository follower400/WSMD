"""核心链路单元测试（离线、无需下载模型）。

覆盖：settings 配置与开关、LocalVectorStore 检索/过滤/边缘、
ChromaVectorStore 仓储契约（mock 底层）、知识库归一化、LLM JSON 解析边缘、
调解主链路规则回退与知识检索接口。
"""
import pytest
from fastapi.testclient import TestClient

from api import settings
from data.vector_db import ChromaVectorStore, LocalVectorStore
import repositories.knowledge_repository as knowledge_repository
from repositories.knowledge_repository import (
    _normalize_legal_payload,
    _normalize_case_payload,
)
from services.llm_generation_service import (
    _extract_json_text,
    _parse_json_payload,
    LLMGenerationError,
)


# ---------- settings ----------
def test_settings_constants_present():
    assert settings.LEGAL_KB_PATH.name == "legal_knowledge_base.json"
    assert settings.CASE_KB_PATH.name == "case_knowledge_base.json"
    assert settings.CASE_COLLECTION_NAME
    assert settings.INGEST_CHUNK_SIZE > 0
    assert settings.LAW_SOURCE_EXPORT.name == "laws.jsonl"


@pytest.mark.parametrize(
    "provider,enabled",
    [("ollama", True), ("openai", False), ("aliyun", False), ("rule", False)],
)
def test_llm_generation_enabled(monkeypatch, provider, enabled):
    monkeypatch.setattr(settings, "LLM_ENABLED", True)
    monkeypatch.setattr(settings, "RAG_ENABLED", True)
    monkeypatch.setattr(settings, "GENERATION_MODEL", "test-model")
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", provider)
    monkeypatch.setattr(settings, "OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "ALIYUN_LLM_KEY", "")
    assert settings.llm_generation_enabled() is enabled


def test_llm_disabled_switch(monkeypatch):
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    assert settings.llm_generation_enabled() is False


# ---------- Backend selection ----------
@pytest.mark.parametrize(
    "chroma_is_available,expected_backend",
    [(True, "chromadb"), (False, "local_json")],
)
def test_auto_backend_prefers_chroma_and_falls_back_to_json(
    monkeypatch, chroma_is_available, expected_backend
):
    monkeypatch.setattr(settings, "KNOWLEDGE_BACKEND", "auto")
    monkeypatch.setattr(knowledge_repository, "chroma_available", lambda: chroma_is_available)
    knowledge_repository.active_backend_name.cache_clear()
    try:
        assert knowledge_repository.active_backend_name() == expected_backend
    finally:
        knowledge_repository.active_backend_name.cache_clear()


# ---------- LocalVectorStore ----------
def _law_items():
    return [
        {
            "id": "l1",
            "title": "民法典",
            "article": "288",
            "excerpt": "相邻关系 噪音 装修",
            "dispute_type": "邻里纠纷",
            "region": "全国",
            "keywords": ["噪音", "邻居"],
        }
    ]


def test_local_search_hit_contract():
    store = LocalVectorStore(_law_items(), text_fields=["title", "article", "excerpt"])
    hits = store.search("噪音", dispute_type="邻里纠纷", region="北京")
    assert hits, "全国性法规应匹配任意地域"
    assert hits[0].payload["id"] == "l1"
    assert "噪音" in hits[0].matched_tokens
    assert hits[0].score > 0


def test_local_search_empty_query_and_empty_store():
    store = LocalVectorStore(_law_items(), text_fields=["title", "excerpt"])
    assert store.search("") == []
    assert LocalVectorStore([], text_fields=["title"]).search("噪音") == []


def test_local_search_region_filter_excludes_other_region():
    items = [{"id": "l2", "title": "x", "excerpt": "噪音", "dispute_type": "邻里纠纷", "region": "上海", "keywords": ["噪音"]}]
    store = LocalVectorStore(items, text_fields=["title", "excerpt"])
    assert store.search("噪音", region="北京") == []


def test_local_search_dispute_type_filter():
    store = LocalVectorStore(_law_items(), text_fields=["title", "excerpt"])
    assert store.search("噪音", dispute_type="物业纠纷") == []


# ---------- ChromaVectorStore（mock 底层，避免加载模型）----------
class _FakeDB:
    def __init__(self):
        self.where = None

    def search_with_metadata(self, query, top_k=5, where=None):
        self.where = where
        return [{"text": "t", "metadata": {"id": "x", "dispute_type": "邻里纠纷"}, "score": 0.9}]


class _FakeCollection:
    def count(self):
        return 5


class _FakeClient:
    def get_collection(self, name):
        return _FakeCollection()


def test_chroma_search_contract(monkeypatch):
    store = ChromaVectorStore("test_col")
    fake_db = _FakeDB()
    monkeypatch.setattr(store, "_ensure_db", lambda: fake_db)
    hits = store.search("噪音", dispute_type="邻里纠纷", limit=3)
    assert hits[0].payload["id"] == "x"
    assert hits[0].score == 0.9
    assert hits[0].matched_tokens == []
    store.search("噪音", dispute_type="邻里纠纷", region="北京", limit=3)
    assert fake_db.where == {
        "$and": [
            {"dispute_type": "邻里纠纷"},
            {"region": {"$in": ["全国", "北京"]}},
        ]
    }
    assert store.search("") == []


def test_chroma_count_and_available(monkeypatch):
    store = ChromaVectorStore("test_col")
    monkeypatch.setattr(store, "_client", lambda: _FakeClient())
    assert store.count() == 5
    assert store.is_available() is True


# ---------- 知识库归一化 ----------
def test_normalize_legal_and_case():
    law = _normalize_legal_payload({"id": "l1", "title": "民法典", "article": "288", "excerpt": "x"}, score=0.5, matched_tokens=["噪音"])
    assert law.id == "l1" and law.title == "民法典" and law.score == 0.5
    case = _normalize_case_payload({"id": "c1", "title": "案例", "summary": "s"}, score=0.3, matched_tokens=[])
    assert case.id == "c1" and case.summary == "s"


def test_normalize_missing_fields():
    law = _normalize_legal_payload({}, score=0.0, matched_tokens=[])
    assert law.id == "unknown-law" and law.title == "未知法规"
    case = _normalize_case_payload({}, score=0.0, matched_tokens=[])
    assert case.id == "unknown-case"


# ---------- LLM JSON 解析边缘 ----------
def test_extract_json_strips_wrappers():
    assert _extract_json_text('```json\n{"a":1}\n```') == '{"a":1}'
    assert _extract_json_text('{"a":1}') == '{"a":1}'


def test_parse_json_payload_ok_and_error():
    assert _parse_json_payload('{"summary":"s","steps":[]}') == {"summary": "s", "steps": []}
    with pytest.raises(LLMGenerationError):
        _parse_json_payload("不是 JSON")


# ---------- 主链路（离线规则回退）----------
@pytest.fixture()
def client():
    from api.main import app
    return TestClient(app)


@pytest.fixture()
def local_json_backend(monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_BACKEND", "local_json")
    knowledge_repository.clear_caches()
    yield
    knowledge_repository.clear_caches()


def test_mediate_rule_fallback(client, monkeypatch, local_json_backend):
    monkeypatch.setattr(settings, "LLM_ENABLED", False)
    monkeypatch.setattr(settings, "RAG_ENABLED", False)
    resp = client.post("/mediate", json={"description": "邻居装修噪音太大影响休息", "preferred_region": "北京"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dispute_type"] == "邻里纠纷"
    assert data["legal_basis"] and data["case_references"]
    assert data["steps"] and data["emotion_guidance"]


def test_knowledge_search_filters(client, local_json_backend):
    resp = client.get("/knowledge/search", params={"q": "噪音", "dispute_type": "邻里纠纷", "region": "北京"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_legal"] >= 1
    assert data["total_cases"] >= 1


def test_health_and_runtime(client):
    health = client.get("/health").json()
    assert health["knowledge_base_loaded"] is True
    runtime = client.get("/system/runtime-profile").json()
    assert runtime["counts"]["legal_items"] >= 1
    assert runtime["counts"]["case_items"] >= 1
    assert runtime["runtime"]["generation_mode"] in {"rule_based", "rag_llm"}