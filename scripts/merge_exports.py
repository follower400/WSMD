#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def iter_records_from_dir(directory: Path) -> Iterable[dict]:
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        if path.suffix.lower() == ".jsonl":
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        else:
            data = json.load(path.open("r", encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    yield item
            elif isinstance(data, dict):
                yield data


def write_jsonl(records: Iterable[dict], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="合并多份 JSON/JSONL 导出文件")
    parser.add_argument("--laws-dir", type=Path, required=True)
    parser.add_argument("--cases-dir", type=Path, required=True)
    parser.add_argument("--out-laws", type=Path, default=Path("storage/raw/laws.jsonl"))
    parser.add_argument("--out-cases", type=Path, default=Path("storage/raw/cases.jsonl"))
    args = parser.parse_args()

    law_count = write_jsonl(iter_records_from_dir(args.laws_dir), args.out_laws)
    case_count = write_jsonl(iter_records_from_dir(args.cases_dir), args.out_cases)

    print(json.dumps({
        "status": "ok",
        "laws_written": law_count,
        "cases_written": case_count,
        "out_laws": str(args.out_laws),
        "out_cases": str(args.out_cases),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
