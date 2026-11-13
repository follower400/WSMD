#!/usr/bin/env python3
"""一键构建真实检索库并启动后端前的准备脚本。"""
from ingestion.build_chroma_db import main

if __name__ == "__main__":
    raise SystemExit(main())
