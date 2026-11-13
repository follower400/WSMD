#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

LAW_REQUIRED = {"id", "title", "article", "content", "region", "dispute_type"}
CASE_REQUIRED = {"id", "title", "summary", "content", "region", "dispute_type"}


def iter_records(path: Path) -> Iterable[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path} 第 {lineno} 行 JSON 解析失败: {e}")
    else:
        data = json.load(path.open("r", encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path} 必须是数组 JSON 或 JSONL")
        for item in data:
            yield item


def validate(path: Path, required: set[str], label: str) -> tuple[int, int]:
    total = 0
    errors = 0
    for index, record in enumerate(iter_records(path), start=1):
        total += 1
        missing = [k for k in sorted(required) if not record.get(k)]
        if missing:
            errors += 1
            print(f"[ERROR] {label} 第 {index} 条缺少字段: {', '.join(missing)}")
    if total == 0:
        print(f"[WARN] {label} 文件为空: {path}")
    else:
        print(f"[OK] {label} 共检测 {total} 条")
    return total, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验法规/案例导入文件")
    parser.add_argument("--laws", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    args = parser.parse_args()

    law_total, law_errors = validate(args.laws, LAW_REQUIRED, "法规")
    case_total, case_errors = validate(args.cases, CASE_REQUIRED, "案例")

    print("-" * 50)
    print(f"法规: {law_total} 条, 错误 {law_errors} 条")
    print(f"案例: {case_total} 条, 错误 {case_errors} 条")

    return 1 if (law_errors or case_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
