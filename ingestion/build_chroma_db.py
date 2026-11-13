#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import os

from api import settings
from data.vector_db import ChromaVectorStore, build_embedder
from repositories.knowledge_repository import clear_caches
# HuggingFace 镜像（便于国内下载 embedding 模型）；不覆盖用户已设置的值
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            for sep in ["。", "；", "！", "？", "\n", ";"]:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + chunk_size // 2:
                    end = last_sep + 1
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < text_len else text_len
    return chunks


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".jsonl":
        records = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def load_fallback_records(path: Path, source_type: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        items = json.load(f)
    records: list[dict[str, Any]] = []
    for item in items:
        base = dict(item)
        base["source_type"] = source_type
        if source_type == "law":
            base.setdefault("content", item.get("excerpt", ""))
        else:
            base.setdefault("content", item.get("summary", ""))
        records.append(base)
    return records


def normalize_law(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id") or record.get("doc_id") or record.get("law_id") or "law-unknown"),
        "title": str(record.get("title") or record.get("law_name") or "未知法规"),
        "article": str(record.get("article") or record.get("article_no") or record.get("article_id") or ""),
        "content": str(record.get("content") or record.get("excerpt") or ""),
        "source_url": record.get("source_url"),
        "effective_status": record.get("effective_status"),
        "region": record.get("region") or record.get("jurisdiction") or "全国",
        "dispute_type": record.get("dispute_type"),
        "keywords": list(record.get("keywords") or []),
        "law_type": record.get("law_type") or "法律",
        "source_level": record.get("source_level") or ("local" if "北京" in str(record.get("region") or "") else "national"),
    }


def normalize_case(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(record.get("id") or record.get("doc_id") or record.get("case_id") or "case-unknown"),
        "title": str(record.get("title") or "未知案例"),
        "summary": str(record.get("summary") or record.get("content") or ""),
        "content": str(record.get("content") or record.get("summary") or ""),
        "source_url": record.get("source_url"),
        "region": record.get("region") or record.get("jurisdiction") or "全国",
        "dispute_type": record.get("dispute_type") or "一般民事纠纷",
        "keywords": list(record.get("keywords") or []),
        "handling_points": list(record.get("handling_points") or []),
    }


def build_documents(records: list[dict[str, Any]], source_type: str, chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for record in records:
        normalized = normalize_law(record) if source_type == "law" else normalize_case(record)
        chunks = chunk_text(normalized.pop("content"), chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            continue
        for index, chunk in enumerate(chunks):
            metadata = dict(normalized)
            metadata["source_type"] = source_type
            metadata["chunk_index"] = index
            metadata["document"] = chunk
            if source_type == "law":
                metadata.setdefault("excerpt", chunk)
            else:
                metadata.setdefault("summary", chunk)
            docs.append(
                {
                    "id": f"{normalized['id']}-chunk-{index}",
                    "document": chunk,
                    "metadata": metadata,
                }
            )
    return docs


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Chroma 真实检索库")
    parser.add_argument("--laws", type=str, default=str(settings.LAW_SOURCE_EXPORT), help="法规 JSON/JSONL 导出文件")
    parser.add_argument("--cases", type=str, default=str(settings.CASE_SOURCE_EXPORT), help="案例 JSON/JSONL 导出文件")
    parser.add_argument("--rebuild", action="store_true", help="重建 collection")
    parser.add_argument("--chunk-size", type=int, default=settings.INGEST_CHUNK_SIZE)
    parser.add_argument("--overlap", type=int, default=settings.INGEST_CHUNK_OVERLAP)
    args = parser.parse_args()

    laws_path = Path(args.laws)
    cases_path = Path(args.cases)

    law_records = read_records(laws_path) or load_fallback_records(settings.LEGAL_KB_PATH, "law")
    case_records = read_records(cases_path) or load_fallback_records(settings.CASE_KB_PATH, "case")

    law_docs = build_documents(law_records, "law", args.chunk_size, args.overlap)
    case_docs = build_documents(case_records, "case", args.chunk_size, args.overlap)

    # ensure embedder can initialize before clearing collections
    embedder = build_embedder()
    law_store = ChromaVectorStore(settings.LAW_COLLECTION_NAME, embedder=embedder)
    case_store = ChromaVectorStore(settings.CASE_COLLECTION_NAME, embedder=embedder)

    if args.rebuild:
        law_store.clear()
        case_store.clear()

    inserted_laws = law_store.add_documents(law_docs)
    inserted_cases = case_store.add_documents(case_docs)
    clear_caches()

    print(json.dumps(
        {
            "status": "ok",
            "law_collection": settings.LAW_COLLECTION_NAME,
            "case_collection": settings.CASE_COLLECTION_NAME,
            "legal_chunks": inserted_laws,
            "case_chunks": inserted_cases,
            "chroma_dir": str(settings.CHROMA_DIR),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
