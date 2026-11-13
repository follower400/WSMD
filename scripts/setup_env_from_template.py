#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '.env'

TEMPLATE = '''KNOWLEDGE_BACKEND=auto
VECTOR_BACKEND=auto
CHROMA_MODE=persistent
CHROMA_PERSIST_DIR=./storage/chroma
LAW_SOURCE_EXPORT=./storage/raw/laws.jsonl
CASE_SOURCE_EXPORT=./storage/raw/cases.jsonl
OPENAI_API_KEY=
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
GENERATION_PROVIDER=openai
GENERATION_MODEL=gpt-5.2
LLM_ENABLED=true
RAG_ENABLED=true
'''

if TARGET.exists():
    print(f"已存在: {TARGET}")
else:
    TARGET.write_text(TEMPLATE, encoding='utf-8')
    print(f"已生成: {TARGET}")
    print('请手动填入 OPENAI_API_KEY')
