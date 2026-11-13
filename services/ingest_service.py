from pathlib import Path

from api import settings
from api.models import IngestBuildResponse
from ingestion.build_chroma_db import build_documents, load_fallback_records, read_records
from repositories.knowledge_repository import clear_caches
from data.vector_db import ChromaVectorStore, build_embedder
from services.legal_kb_service import get_runtime_profile


def build_real_knowledge_base(laws_path: str | None = None, cases_path: str | None = None, rebuild: bool = False) -> IngestBuildResponse:
    law_records = read_records(Path(laws_path)) if laws_path else []
    case_records = read_records(Path(cases_path)) if cases_path else []
    if not law_records:
        law_records = load_fallback_records(settings.LEGAL_KB_PATH, "law")
    if not case_records:
        case_records = load_fallback_records(settings.CASE_KB_PATH, "case")

    law_docs = build_documents(law_records, "law", settings.INGEST_CHUNK_SIZE, settings.INGEST_CHUNK_OVERLAP)
    case_docs = build_documents(case_records, "case", settings.INGEST_CHUNK_SIZE, settings.INGEST_CHUNK_OVERLAP)

    embedder = build_embedder()
    law_store = ChromaVectorStore(settings.LAW_COLLECTION_NAME, embedder=embedder)
    case_store = ChromaVectorStore(settings.CASE_COLLECTION_NAME, embedder=embedder)

    if rebuild:
        law_store.clear()
        case_store.clear()

    inserted_laws = law_store.add_documents(law_docs)
    inserted_cases = case_store.add_documents(case_docs)
    clear_caches()

    return IngestBuildResponse(
        status="ok",
        legal_chunks=inserted_laws,
        case_chunks=inserted_cases,
        law_collection=settings.LAW_COLLECTION_NAME,
        case_collection=settings.CASE_COLLECTION_NAME,
        runtime=get_runtime_profile(),
    )
