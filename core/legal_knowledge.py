# core/legal_knowledge.py
"""中文法律语料库的法律知识分块模块。"""

from __future__ import annotations
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import json
import hashlib
import logging
import os
import re
import time
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, Iterator, List, Optional, Sequence, Tuple
import logging

LOGGER = logging.getLogger("legal_chunking")
logger=LOGGER
AUDIT_LOGGER = logging.getLogger("legal_validation_audit")


def configure_logging(level: int = logging.INFO) -> None:
    if LOGGER.handlers:
        return
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(level)


def configure_audit_logging(level: int = logging.INFO) -> None:
    if AUDIT_LOGGER.handlers:
        return
    audit_dir = Path("audit")
    audit_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(audit_dir / "legal_validation.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    file_handler.setFormatter(formatter)
    AUDIT_LOGGER.addHandler(file_handler)
    AUDIT_LOGGER.setLevel(level)


@dataclass
class LegalChunk:
    """法律条文分块数据结构（扩展版，兼容构建器）"""
    content: str
    law_name: str = ""
    article_no: str = ""
    source_type: str = "法律"
    chunk_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    is_valid: bool
    confidence: float
    rejection_reason: List[str]
    metadata: Dict[str, Any]
    warning_flags: List[str] = field(default_factory=list)
    severity: str = "pass"


@dataclass(frozen=True)
class ChunkingConfig:
    max_chunk_size: int = 500
    overlap_size: int = 50
    sentence_separators: str = "。；？！;?!"
    clause_patterns: Tuple[str, ...] = (
        r"(第[零一二三四五六七八九十百千万0-9IVXLCM]+款)",
        r"(（[一二三四五六七八九十百千万]+）)",
    )
    source_name: str = "STARD"
    hard_max_chunk_size: int = 2000

    @classmethod
    def from_env(cls) -> "ChunkingConfig":
        return cls(
            max_chunk_size=int(os.getenv("LEGAL_CHUNK_MAX_SIZE", "500")),
            overlap_size=int(os.getenv("LEGAL_CHUNK_OVERLAP", "50")),
            sentence_separators=os.getenv("LEGAL_SENTENCE_SEPARATORS", "。；？！;?!"),
            source_name=os.getenv("LEGAL_CHUNK_SOURCE", "STARD"),
            hard_max_chunk_size=int(os.getenv("LEGAL_CHUNK_HARD_MAX", "2000")),
        )


class LegalTextPreprocessor:
    _whitespace_re = re.compile(r"[ \t\r\f\v]+")
    _newline_re = re.compile(r"\n+")

    def preprocess_text(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        normalized = unicodedata.normalize("NFKC", text)
        normalized = self._whitespace_re.sub(" ", normalized)
        normalized = self._newline_re.sub("\n", normalized).strip()
        return normalized


class HierarchyParser:
    _article_re = re.compile(r"^(?P<law_name>.*?)(?:第(?P<article_cn>[零一二三四五六七八九十百千万0-9IVXLCM]+)条)$")
    _clause_re = re.compile(r"(第[零一二三四五六七八九十百千万0-9IVXLCM]+款)")
    _item_re = re.compile(r"(（[一二三四五六七八九十百千万]+）)")
    _enum_intro_re = re.compile(r"(下列情形之一|有下列|包括以下|如下)")
    _cn_num_map = {
        "零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000,
    }

    def parse_legal_structure(self, name: str) -> Dict[str, Any]:
        if not name or not isinstance(name, str):
            return {"law_name": "UNKNOWN", "article_no": "0"}
        title = unicodedata.normalize("NFKC", name).strip()
        matched = self._article_re.match(title)
        if matched:
            law_name = matched.group("law_name").strip() or "UNKNOWN"
            article_raw = matched.group("article_cn")
            return {"law_name": law_name, "article_no": self._normalize_number(article_raw)}
        return {"law_name": title, "article_no": "0"}

    def detect_hierarchy(self, text: str) -> str:
        if self._item_re.search(text):
            return "item"
        if self._clause_re.search(text):
            return "clause"
        return "article"

    def split_by_clause(self, text: str) -> List[str]:
        return self._split_keep_delimiter(text, self._clause_re)

    def split_by_item(self, text: str) -> List[str]:
        return self._split_keep_delimiter(text, self._item_re)

    def likely_enumeration_intro(self, text: str) -> bool:
        return bool(self._enum_intro_re.search(text))

    def _normalize_number(self, raw: str) -> str:
        raw = raw.strip()
        if raw.isdigit():
            return str(int(raw))
        roman_candidate = raw.upper()
        if re.fullmatch(r"[IVXLCM]+", roman_candidate):
            return str(self._roman_to_int(roman_candidate))
        cn_val = self._chinese_to_int(raw)
        return str(cn_val) if cn_val is not None else raw

    @staticmethod
    def _roman_to_int(roman: str) -> int:
        mapping = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
        total = 0
        prev = 0
        for c in reversed(roman):
            val = mapping[c]
            if val < prev:
                total -= val
            else:
                total += val
                prev = val
        return total

    def _chinese_to_int(self, text: str) -> Optional[int]:
        if not text:
            return None
        if all(ch in "零一二三四五六七八九" for ch in text):
            return int("".join(str(self._cn_num_map[ch]) for ch in text))
        unit = 0
        ldig = []
        for c in reversed(text):
            val = self._cn_num_map.get(c)
            if val is None:
                return None
            if val >= 10:
                if val > unit:
                    unit = val
                    ldig.append(val)
                else:
                    ldig[-1] = ldig[-1] * val
            else:
                if unit:
                    ldig.append(unit * val)
                else:
                    ldig.append(val)
        if unit == 10 and len(ldig) == 1:
            ldig.append(10)
        return sum(ldig)

    @staticmethod
    def _split_keep_delimiter(text: str, pattern: re.Pattern) -> List[str]:
        pieces = pattern.split(text)
        if len(pieces) <= 1:
            return [text] if text else []
        result = []
        buffer = ""
        for part in pieces:
            if not part:
                continue
            if pattern.fullmatch(part):
                if buffer.strip():
                    result.append(buffer.strip())
                buffer = part
            else:
                buffer += part
        if buffer.strip():
            result.append(buffer.strip())
        return result


class ChunkValidator:
    def __init__(self, max_chunk_size: int, hard_max_chunk_size: int) -> None:
        self.max_chunk_size = max_chunk_size
        self.hard_max_chunk_size = hard_max_chunk_size

    def validate_chunk(self, chunk: Dict[str, Any]) -> bool:
        if not isinstance(chunk, dict):
            return False
        text = chunk.get("text")
        if not isinstance(text, str) or not text.strip():
            return False
        if len(text) > self.hard_max_chunk_size:
            return False
        metadata = chunk.get("metadata", {})
        required_fields = {"law_name", "article_no", "original_id", "source", "char_count", "token_estimate", "chunk_index", "chunk_strategy", "hierarchy"}
        if not required_fields.issubset(metadata.keys()):
            return False
        if metadata["char_count"] != len(text):
            return False
        return True


class STARDAdapter:
    REQUIRED_FIELDS = {"id", "name", "content"}

    def iter_corpus(self, path: str | Path) -> Iterator[Dict[str, Any]]:
        """终极版：适配混合格式的STARD语料库"""
        fp = Path(path)
        if not fp.exists():
            raise FileNotFoundError(f"STARD file not found: {fp}")

        # 策略1: 读取整个文件作为JSON数组（你的文件实际是这种格式！）
        try:
            with fp.open("r", encoding="utf-8-sig") as f:  # 自动处理BOM
                data = json.load(f)

            # 如果整个文件是JSON数组
            if isinstance(data, list):
                for idx, item in enumerate(data):
                    # 如果数组元素是字符串（你的日志显示是字符串键值对）
                    if isinstance(item, str) and ':' in item:
                        try:
                            # 尝试修复成合法JSON对象
                            fixed_json = "{" + item.strip().rstrip(',').rstrip('}') + "}"
                            item = json.loads(fixed_json)
                        except:
                            continue

                    # 标准化字段
                    yield self._validate_item(item, idx)
                return

        except json.JSONDecodeError:
            pass

        # 策略2: 按行解析（备用）
        with fp.open("r", encoding="utf-8-sig") as infile:
            for line_no, line in enumerate(infile, 1):
                try:
                    # 清洗：移除行首尾的非法字符
                    clean_line = line.strip().rstrip(',').rstrip('}').lstrip('{')
                    if not clean_line:
                        continue

                    # 你的文件典型特征：行内是 "key": "value" 对
                    if ':' in clean_line and not clean_line.startswith('['):
                        # 强制包装成合法JSON对象
                        json_str = f'{{{clean_line}}}'
                        item = json.loads(json_str)
                        yield self._validate_item(item, line_no)
                except Exception as e:
                    LOGGER.debug(f"跳过无效行 {line_no}: {str(e)[:50]} | {line[:30]}...")

    def _validate_item(self, item: Any, line_no: int) -> Dict[str, Any]:
        """终极字段映射（专治你的日志问题）"""
        # 如果传入的是字符串（你的日志显示有字符串键值对）
        if isinstance(item, str) and ':' in item:
            try:
                # 从字符串中提取关键字段
                item_dict = {}
                for field in ['id', 'name', 'content']:
                    # 匹配 "id": 123 或 "id": "abc"
                    match = re.search(rf'"{field}"\s*:\s*(\d+|"[^"]*")', item)
                    if match:
                        val = match.group(1).strip('"')
                        item_dict[field] = val if field == 'id' else str(val)
                item = item_dict
            except:
                item = {}

        # 确保是字典
        if not isinstance(item, dict):
            item = {}

        # 字段智能映射（你的日志显示字段名混乱）
        field_map = {
            'id': ['id', 'ID', 'doc_id', 'match_id'],
            'name': ['name', 'title', 'law_name', '问题', '法规名称'],
            'content': ['content', 'text', 'body', '相关法规', '法规内容']
        }

        result = {}
        for std_field, candidates in field_map.items():
            for cand in candidates:
                if cand in item:
                    result[std_field] = str(item[cand])
                    break
            else:
                # 特殊处理：当字段名是法规条文时（你的日志特征）
                if std_field == 'name' and '中华人民共和国' in str(item):
                    result['name'] = list(item.keys())[0]  # 取第一个键名
                    result['content'] = str(list(item.values())[0])
                    break
                result[std_field] = "unknown" if std_field == 'id' else ""

        # 强制补全缺失字段（防止报错）
        if result['id'] == "unknown":
            result['id'] = f"auto_{line_no}"
        if not result['name'].strip():
            result['name'] = f"法规文档_{line_no}"
        if not result['content'].strip():
            result['content'] = "（内容缺失）"

        return result

class LegalContentValidator:
    _article_pattern = re.compile(r"第[零一二三四五六七八九十百千万0-9IVXLCM]+条(?:之[零一二三四五六七八九十百千万0-9IVXLCM]+)?(?:第[零一二三四五六七八九十百千万0-9IVXLCM]+款)?")
    _law_name_pattern = re.compile(r"《[^》]+》(?:（[^）]*(?:全国人民代表大会|国务院|最高人民法院|司法部|人民代表大会|人民政府)[^）]*）)?(?:（\d{4}年(?:修订|修正|制定|施行)?[^）]*）)?")
    _invalid_markers = ("已废止", "被修改", "不再适用")
    _replacement_markers = ("修正后", "修订后", "替代条文", "现行", "依据")
    _warning_markers = ("过渡性规定", "司法解释冲突条款", "部分修正", "参照适用", "可以参照")
    _normative_markers = ("应当", "不得", "可以", "必须", "有权", "责任", "义务", "处罚")
    _law_conflict_signatures = {"民法典": ("犯罪", "刑罚", "有期徒刑", "拘役"), "刑法": ("民事法律行为", "婚姻家庭", "物权")}
    _source_type_map = {"法律": "法律", "行政法规": "行政法规", "司法解释": "司法解释", "地方法规": "地方法规"}

    def __init__(self) -> None:
        configure_audit_logging()

    def validate_legal_content(self, chunk: LegalChunk, strict_mode: bool = True) -> ValidationResult:
        rejection_reasons = []
        warning_flags = []
        confidence = 1.0

        content = (chunk.content or "").strip()
        law_name = (chunk.law_name or "").strip()
        article_no = (chunk.article_no or "").strip()

        if len(content) < 15:
            rejection_reasons.append("格式错误:内容长度不足15字符")
        if not self._contains_valid_article(article_no):
            rejection_reasons.append("格式错误:条文编号不符合标准格式")
        if not self._contains_valid_law_name(law_name):
            if strict_mode:
                rejection_reasons.append("格式错误:法律名称缺少标准元信息")
            else:
                warning_flags.append("法律名称元信息不完整")
                confidence -= 0.1
        if not content:
            rejection_reasons.append("数据残缺:条文内容为空")
        elif not self._has_normative_elements(content):
            rejection_reasons.append("数据残缺:缺少法律规范构成要件")
        if self._has_invalidity_marker(content) and not self._has_replacement(content):
            rejection_reasons.append("内容失效:检测到失效标识且无替代条文")
        if self._law_content_conflict(law_name, content):
            rejection_reasons.append("条文冲突:法律名称与内容语义不匹配")
        for marker in self._warning_markers:
            if marker in content:
                warning_flags.append(f"时效性告警:{marker}")
                confidence = min(confidence, 0.3)
        if warning_flags and not rejection_reasons and confidence > 0.3:
            confidence = 0.3

        is_valid = len(rejection_reasons) == 0
        if not is_valid:
            confidence = 0.0

        result = ValidationResult(
            is_valid=is_valid,
            confidence=max(0.0, min(1.0, confidence)),
            rejection_reason=rejection_reasons,
            metadata={
                "audit_time": self._now_iso8601(),
                "validation_hash": self._validation_hash(chunk),
                "legal_effect_level": self._infer_effect_level(chunk.source_type),
                "law_hierarchy": self._infer_effect_level(chunk.source_type),
                "strict_mode": strict_mode,
            },
            warning_flags=warning_flags,
            severity="reject" if rejection_reasons else ("warn" if warning_flags else "pass"),
        )
        self._log_audit(chunk, result)
        return result

    def generate_audit_report(self, validated_rows: Sequence[Tuple[LegalChunk, ValidationResult]]) -> Dict[str, Any]:
        hierarchy_counter = Counter()
        rejection_counter = Counter()
        severity_counter = Counter()
        warning_counter = Counter()
        details = []
        for chunk, result in validated_rows:
            hierarchy = self._infer_effect_level(chunk.source_type)
            hierarchy_counter[hierarchy] += 1
            severity_counter[result.severity] += 1
            for reason in result.rejection_reason:
                rejection_counter[self._reason_category(reason)] += 1
            for warning in result.warning_flags:
                warning_counter[warning] += 1
            details.append({"law_name": chunk.law_name, "article_no": chunk.article_no, "source_type": chunk.source_type, "validation": asdict(result)})
        return {
            "metadata_standard": "司法大数据元数据规范（2023版）",
            "generated_at": self._now_iso8601(),
            "dataset_overview": {"total_records": len(validated_rows), "hierarchy_stats": dict(hierarchy_counter), "severity_stats": dict(severity_counter)},
            "rejection_reason_stats": {"格式错误": rejection_counter.get("格式错误", 0), "内容失效": rejection_counter.get("内容失效", 0), "条文冲突": rejection_counter.get("条文冲突", 0), "数据残缺": rejection_counter.get("数据残缺", 0)},
            "warning_stats": dict(warning_counter),
            "records": details,
        }

    def export_audit_report_json(self, report: Dict[str, Any], output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return output

    def export_audit_report_pdf(self, report: Dict[str, Any], output_path: str | Path) -> Path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            AUDIT_LOGGER.error("PDF export failed: reportlab missing err=%s", exc)
            raise RuntimeError("PDF导出依赖reportlab，请先安装: pip install reportlab") from exc
        c = canvas.Canvas(str(output), pagesize=A4)
        _, height = A4
        y = height - 40
        lines = ["司法审计审核报告模板", f"生成时间: {report.get('generated_at', '')}", f"标准: {report.get('metadata_standard', '')}", f"总条目数: {report.get('dataset_overview', {}).get('total_records', 0)}", "拒绝原因统计:"]
        for key, val in report.get("rejection_reason_stats", {}).items():
            lines.append(f"  - {key}: {val}")
        lines.append("法律层级统计:")
        for key, val in report.get("dataset_overview", {}).get("hierarchy_stats", {}).items():
            lines.append(f"  - {key}: {val}")
        for line in lines:
            c.drawString(40, y, line[:90])
            y -= 18
            if y < 60:
                c.showPage()
                y = height - 40
        c.save()
        return output

    def _contains_valid_article(self, article_no: str) -> bool:
        return bool(self._article_pattern.search(article_no))

    def _contains_valid_law_name(self, law_name: str) -> bool:
        return bool(self._law_name_pattern.search(law_name))

    def _has_normative_elements(self, content: str) -> bool:
        marker_hits = sum(1 for marker in self._normative_markers if marker in content)
        return marker_hits >= 1 and len(content) >= 15

    def _has_invalidity_marker(self, content: str) -> bool:
        return any(marker in content for marker in self._invalid_markers)

    def _has_replacement(self, content: str) -> bool:
        return any(marker in content for marker in self._replacement_markers)

    def _law_content_conflict(self, law_name: str, content: str) -> bool:
        for law_key, keywords in self._law_conflict_signatures.items():
            if law_key in law_name:
                return any(token in content for token in keywords)
        return False

    def _infer_effect_level(self, source_type: str) -> str:
        return self._source_type_map.get(source_type, "其他规范性文件")

    @staticmethod
    def _reason_category(reason: str) -> str:
        return reason.split(":", 1)[0] if ":" in reason else reason

    @staticmethod
    def _validation_hash(chunk: LegalChunk) -> str:
        return hashlib.sha256(f"{chunk.source_type}|{chunk.law_name}|{chunk.article_no}|{chunk.content}".encode("utf-8")).hexdigest()

    @staticmethod
    def _now_iso8601() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _log_audit(self, chunk: LegalChunk, result: ValidationResult) -> None:
        AUDIT_LOGGER.info("law=%s article=%s source=%s valid=%s confidence=%.2f reason=%s warnings=%s hash=%s",
                          chunk.law_name, chunk.article_no, chunk.source_type, result.is_valid, result.confidence,
                          "|".join(result.rejection_reason), "|".join(result.warning_flags), result.metadata.get("validation_hash", ""))


def validate_legal_content(chunk: LegalChunk, strict_mode: bool = True) -> ValidationResult:
    return LegalContentValidator().validate_legal_content(chunk, strict_mode=strict_mode)


class LegalChunkingStrategy:
    def __init__(self, max_chunk_size: int = 500, overlap_size: int = 50, sentence_separators: str = "。；？！;?!", clause_patterns: Optional[List[str]] = None) -> None:
        configure_logging()
        self.config = ChunkingConfig(
            max_chunk_size=max_chunk_size,
            overlap_size=overlap_size,
            sentence_separators=sentence_separators,
            clause_patterns=tuple(clause_patterns) if clause_patterns else ChunkingConfig().clause_patterns,
        )
        self.preprocessor = LegalTextPreprocessor()
        self.parser = HierarchyParser()
        self.validator = ChunkValidator(max_chunk_size=self.config.max_chunk_size, hard_max_chunk_size=ChunkingConfig().hard_max_chunk_size)
        self._sentence_split_re = re.compile("(?<=[{re.escape(self.config.sentence_separators)}])")

    def preprocess_text(self, text: str) -> str:
        return self.preprocessor.preprocess_text(text)

    def parse_legal_structure(self, name: str) -> Dict[str, Any]:
        return self.parser.parse_legal_structure(name)

    def chunk_by_hierarchy(self, content: str) -> List[Dict[str, Any]]:
        text = self.preprocess_text(content)
        if not text:
            return []
        if len(text) <= self.config.max_chunk_size:
            return [{"text": text, "chunk_strategy": "article", "hierarchy": "article"}]
        return self._split_with_priority(text)

    def adaptive_chunking(self, law_name: str, article_no: str, content: str) -> List[Dict[str, Any]]:
        text = self.preprocess_text(content)
        if not text:
            return []
        if len(text) > ChunkingConfig().hard_max_chunk_size:
            LOGGER.warning("ultra-long article detected article_no=%s length=%s", article_no, len(text))
        raw_chunks = self.chunk_by_hierarchy(text)
        merged = self._merge_with_overlap(raw_chunks)
        final_chunks = []
        for idx, part in enumerate(merged, start=1):
            chunk_text = part["text"].strip()
            chunk = self._build_chunk(law_name=law_name, article_no=article_no, content=chunk_text, chunk_index=idx, strategy=part["chunk_strategy"], hierarchy=part["hierarchy"], original_id=-1)
            final_chunks.append(chunk)
        return final_chunks

    def validate_chunk(self, chunk: Dict[str, Any]) -> bool:
        return self.validator.validate_chunk(chunk)

    def process_batch(self, documents: List[Dict[str, Any]], batch_size: int = 100) -> Generator[List[Dict[str, Any]], None, None]:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        total = len(documents)
        started = time.perf_counter()
        for offset in range(0, total, batch_size):
            batch = documents[offset:offset + batch_size]
            processed = []
            for doc in batch:
                processed.extend(self.chunk_document(doc))
            elapsed = max(time.perf_counter() - started, 1e-6)
            throughput = (offset + len(batch)) / elapsed
            LOGGER.info("processed=%s/%s throughput=%.2f docs/s", offset + len(batch), total, throughput)
            yield processed

    def chunk_document(self, document: Dict[str, Any]) -> List[LegalChunk]:
        """返回 LegalChunk 对象列表，兼容构建器"""
        try:
            self._validate_document(document)
        except ValueError as exc:
            LOGGER.error("invalid document id=%s err=%s", document.get("id"), exc)
            return []

        parsed = self.parse_legal_structure(document["name"])
        law_name = parsed["law_name"]
        article_no = parsed["article_no"]
        text = self.preprocess_text(document["content"])

        chunk_parts = self.chunk_by_hierarchy(text)
        merged = self._merge_with_overlap(chunk_parts)

        result = []
        for idx, part in enumerate(merged, start=1):
            chunk_dict = self._build_chunk(
                law_name=law_name,
                article_no=article_no,
                content=part["text"],
                chunk_index=idx,
                strategy=part["chunk_strategy"],
                hierarchy=part["hierarchy"],
                original_id=int(document["id"]),
            )
            if self.validate_chunk(chunk_dict):
                # 转换为 LegalChunk 对象
                meta = chunk_dict["metadata"]
                legal_chunk = LegalChunk(
                    content=chunk_dict["text"],
                    law_name=meta["law_name"],
                    article_no=meta["article_no"],
                    source_type="法律",   # 默认，可根据需要调整
                    chunk_id=chunk_dict["chunk_id"],
                    chunk_index=meta["chunk_index"],
                    total_chunks=len(merged),
                    metadata=meta,
                )
                result.append(legal_chunk)
            else:
                LOGGER.warning("invalid chunk rejected id=%s idx=%s", document["id"], idx)
        return result

    def _split_with_priority(self, text: str) -> List[Dict[str, Any]]:
        clause_parts = self.parser.split_by_clause(text)
        if len(clause_parts) > 1:
            return self._normalize_parts(clause_parts, strategy="clause", hierarchy="clause")
        item_parts = self.parser.split_by_item(text)
        if len(item_parts) > 1:
            return self._normalize_parts(item_parts, strategy="clause", hierarchy="item")
        return self._split_by_sentence(text)

    def _split_by_sentence(self, text: str) -> List[Dict[str, Any]]:
        sentences = [s.strip() for s in self._sentence_split_re.split(text) if s.strip()]
        if not sentences:
            return [{"text": text, "chunk_strategy": "sentence", "hierarchy": "article"}]
        result = []
        buffer = ""
        enum_mode = False
        for sentence in sentences:
            if self.parser.likely_enumeration_intro(sentence):
                enum_mode = True
            if len(buffer) + len(sentence) <= self.config.max_chunk_size:
                buffer += sentence
            else:
                if buffer:
                    result.append({"text": buffer.strip(), "chunk_strategy": "sentence", "hierarchy": "item" if enum_mode else "article"})
                buffer = sentence
            if enum_mode and sentence.endswith("。"):
                enum_mode = False
        if buffer:
            result.append({"text": buffer.strip(), "chunk_strategy": "sentence", "hierarchy": "item" if enum_mode else "article"})
        return result

    def _normalize_parts(self, parts: Sequence[str], strategy: str, hierarchy: str) -> List[Dict[str, Any]]:
        result = []
        for part in parts:
            cleaned = part.strip()
            if not cleaned:
                continue
            if len(cleaned) <= self.config.max_chunk_size:
                result.append({"text": cleaned, "chunk_strategy": strategy, "hierarchy": hierarchy})
            else:
                result.extend(self._split_by_sentence(cleaned))
        return result

    def _merge_with_overlap(self, chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        if self.config.overlap_size <= 0:
            return list(chunks)
        merged = []
        prev_text = ""
        for idx, chunk in enumerate(chunks):
            text = chunk["text"].strip()
            if idx > 0 and prev_text:
                overlap = prev_text[-self.config.overlap_size:]
                text = overlap + text
                if len(text) > ChunkingConfig().hard_max_chunk_size:
                    text = text[-ChunkingConfig().hard_max_chunk_size:]
            merged_chunk = {"text": text, "chunk_strategy": chunk["chunk_strategy"], "hierarchy": chunk["hierarchy"]}
            merged.append(merged_chunk)
            prev_text = chunk["text"]
        return merged

    def _build_chunk(self, law_name: str, article_no: str, content: str, chunk_index: int, strategy: str, hierarchy: str, original_id: int) -> Dict[str, Any]:
        legal_id = self._sanitize_id(f"{law_name}{article_no}chunk{chunk_index}")
        char_count = len(content)
        return {
            "chunk_id": legal_id,
            "text": content,
            "metadata": {
                "law_name": law_name,
                "article_no": article_no,
                "original_id": original_id,
                "source": self.config.source_name,
                "char_count": char_count,
                "token_estimate": (char_count + 3) // 4,
                "chunk_index": chunk_index,
                "chunk_strategy": strategy,
                "hierarchy": hierarchy,
            },
        }

    @staticmethod
    def _sanitize_id(value: str) -> str:
        return re.sub(r"[^\w\-]", "_", value)

    @staticmethod
    def _validate_document(document: Dict[str, Any]) -> None:
        if not isinstance(document, dict):
            raise ValueError("document must be dict")
        for key in ("id", "name", "content"):
            if key not in document:
                raise ValueError(f"missing key: {key}")
        if document["content"] is None:
            raise ValueError("content cannot be null")


def build_chromadb_records(chunks: Iterable[LegalChunk]) -> Dict[str, List[Any]]:
    """将 LegalChunk 对象列表转换为 ChromaDB 需要的格式"""
    ids = []
    docs = []
    metas = []
    for chunk in chunks:
        ids.append(chunk.chunk_id)
        docs.append(chunk.content)
        metas.append(chunk.metadata)
    return {"ids": ids, "documents": docs, "metadatas": metas}