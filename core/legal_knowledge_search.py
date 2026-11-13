"""
智能法律知识检索：基于 LegalVectorDB 语义检索 + 纠纷/地域/层级加权与可解释分析。
"""
from __future__ import annotations
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from data.vector_db import LegalVectorDB

# 法律层级权重：法律 > 司法解释 > 行政法规 > 地方法规
_LAW_LEVEL_WEIGHT: Dict[str, float] = {
    "法律": 1.1,
    "司法解释": 1.05,
    "行政法规": 1.0,
    "地方法规": 0.95,
}

_DISPUTE_KEYWORDS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("物业", "业主", "业委会", "物业费", "公摊"), "物业纠纷"),
    (
        ("买卖合同", "租赁合同", "借款合同", "违约", "定金", "违约金", "履行不能"),
        "合同纠纷",
    ),
    (
        (
            "劳动",
            "劳动合同",
            "解雇",
            "辞退",
            "裁员",
            "加班",
            "工资",
            "社保",
            "工伤",
            "试用期",
            "见习期",
            "终止协议",
            "经济补偿",
            "赔偿金",
            "二倍",
            "用人单位",
            "劳动者",
            "解除劳动关系",
            "解除劳动合同",
        ),
        "劳动纠纷",
    ),
    (
        ("离婚", "婚姻", "抚养", "继承", "赡养", "家事", "共同财产", "财产分割"),
        "婚姻家事",
    ),
    (("商标", "专利", "著作权", "知识产权"), "知识产权"),
    (("交通", "交通事故", "交强险", "第三者"), "交通事故"),
    (("房屋", "拆迁", "征收", "商品房", "安置房"), "房产纠纷"),
)

_BEIJING_HINTS = (
    "北京",
    "北京市",
    "朝阳",
    "朝阳区",
    "海淀",
    "海淀区",
    "东城",
    "西城",
    "丰台",
    "石景山",
    "通州",
    "昌平",
    "大兴",
    "顺义",
    "房山",
    "门头沟",
    "平谷",
    "怀柔",
    "密云",
    "延庆",
)


@dataclass
class LegalSearchResult:
    """单条法律检索结构化结果。"""

    content: str
    source: str
    law_type: str
    similarity: float
    article_no: str
    chunk_id: str
    ai_analysis: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _infer_dispute_type(text: str) -> Optional[str]:
    t = text.strip()
    if not t:
        return None
    if "解除" in t and "合同" in t and "劳动" not in t and "员工" not in t and "用人单位" not in t:
        return "合同纠纷"
    for keywords, label in _DISPUTE_KEYWORDS:
        if any(kw in t for kw in keywords):
            return label
    return None


def _query_mentions_jurisdiction(query: str, jurisdiction_boost: Optional[str]) -> bool:
    if not jurisdiction_boost:
        return False
    if jurisdiction_boost in ("北京", "北京市"):
        return any(k in query for k in _BEIJING_HINTS)
    return jurisdiction_boost in query


def _jurisdiction_blob(meta: Dict[str, Any], law_name: str) -> str:
    for key in ("jurisdiction", "适用地域", "region"):
        v = meta.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return law_name or ""


def _doc_matches_jurisdiction_local(
    law_name: str,
    meta: Dict[str, Any],
    law_type: str,
    jurisdiction_boost: Optional[str],
) -> bool:
    if not jurisdiction_boost or law_type != "地方法规":
        return False
    blob = _jurisdiction_blob(meta, law_name)
    if jurisdiction_boost in ("北京", "北京市"):
        return "北京" in (law_name or "") or "北京" in blob
    return jurisdiction_boost in (law_name or "") or jurisdiction_boost in blob


def _normalize_law_type(raw: str, law_name: str) -> str:
    s = (raw or "").strip()
    if s in _LAW_LEVEL_WEIGHT:
        return s
    name = law_name or ""
    if "解释" in name and ("最高" in name or "最高人民法院" in name):
        return "司法解释"
    if name.startswith("北京市") or name.startswith("北京 "):
        if any(x in name for x in ("条例", "规定", "办法")):
            return "地方法规"
    if "国务院" in name and "条例" in name:
        return "行政法规"
    if "若干问题" in name and "规定" in name:
        return "司法解释"
    if "法" in name and "条例" not in name and "办法" not in name and "规定" not in name:
        if not name.startswith("北京"):
            return "法律"
    if "北京" in name[:6] and any(x in name for x in ("条例", "规定", "办法")):
        return "地方法规"
    if "条例" in name or "办法" in name:
        return "行政法规"
    return "地方法规" if "北京" in name else "法律"


def _metadata_law_type(meta: Dict[str, Any]) -> str:
    for key in ("law_type", "legal_type", "法律类型", "source_type"):
        v = meta.get(key)
        if isinstance(v, str) and v.strip():
            return _normalize_law_type(v, str(meta.get("law_name", "")))
    return _normalize_law_type("", str(meta.get("law_name", "")))


def _int_to_zh_simple(n: int) -> str:
    if n <= 0:
        return str(n)
    digits = "零一二三四五六七八九"
    if n < 10:
        return digits[n]
    if n < 20:
        return ("十" if n == 10 else "十" + digits[n % 10]) if n > 10 else "十"
    if n < 100:
        tens, ones = n // 10, n % 10
        head = digits[tens] + "十"
        if ones == 0:
            return head
        return head + digits[ones]
    return str(n)


def _format_article_no(article_raw: Any) -> str:
    s = str(article_raw or "").strip()
    if not s:
        return ""
    if s == "条":  
        return s
    if "条" in s:
        return s if s.startswith("第") else f"第{s}"
    if s.isdigit():
        return f"第{_int_to_zh_simple(int(s))}条"
    return f"第{s}条"


def _dispute_match_weight(
    expected: Optional[str],
    meta: Dict[str, Any],
) -> Tuple[float, str]:
    if not expected:
        return 1.0, "未指定纠纷类型筛选"
    meta_types: List[str] = []
    for key in ("dispute_type", "纠纷类型", "dispute_tags"):
        v = meta.get(key)
        if isinstance(v, str) and v.strip():
            meta_types.append(v.strip())
        elif isinstance(v, list):
            meta_types.extend(str(x).strip() for x in v if str(x).strip())
    if not meta_types:
        return 1.0, "条文中无纠纷类型元数据，不作降权"
    if any(expected in m or m in expected for m in meta_types):
        return 1.2, f"元数据纠纷类型与「{expected}」一致"
    return 0.4, f"元数据纠纷类型与「{expected}」不一致，降权"


def _region_weight(
    query_hit: bool,
    jurisdiction_boost: Optional[str],
    doc_local_match: bool,
    law_type: str,
) -> Tuple[float, str]:
    if not jurisdiction_boost or not query_hit:
        return 1.0, "未配置地域加权或查询未命中该地域语境"
    if doc_local_match and law_type == "地方法规":
        return 1.3, f"匹配{jurisdiction_boost}地方法规，权重×1.3"
    return 1.0, "查询含地域关键词但本条非该地域地方法规"


def _confidence_label(base: float) -> str:
    if base >= 0.75:
        return "高"
    if base >= 0.5:
        return "中"
    return "低"


def _build_ai_analysis(
    *,
    base_sim: float,
    dispute_w: float,
    region_w: float,
    level_w: float,
    weighted: float,
    law_type: str,
    effective_dispute: Optional[str],
    inferred: Optional[str],
    query: str,
    query_region_hit: bool,
    jurisdiction_boost: Optional[str],
    dispute_note: str,
    region_note: str,
    enable_ai_analysis: bool,
    include_explanation: bool,
) -> Dict[str, Any]:
    if not enable_ai_analysis:
        return {"最终加权得分": round(weighted, 4)}

    scenarios: List[str] = []
    if effective_dispute or inferred:
        dt = effective_dispute or inferred
        scenarios.append(f"{dt}相关检索")
    if query_region_hit and jurisdiction_boost:
        scenarios.append(f"{jurisdiction_boost}地区案件")
    if not scenarios:
        scenarios.append("通用法律检索")

    weight_log = [
        f"纠纷类型×{dispute_w}",
        f"地域规则×{region_w}",
        f"法律层级({law_type})×{level_w}",
    ]

    analysis: Dict[str, Any] = {
        "置信度": _confidence_label(base_sim),
        "适用场景": scenarios,
        "权重调整": weight_log,
        "最终加权得分": round(weighted, 4),
        "基础相似度": round(base_sim, 4),
    }

    if include_explanation:
        steps: List[str] = []
        if inferred or effective_dispute:
            steps.append(
                f"查询分析：推断纠纷类型为「{effective_dispute or inferred}」"
            )
        else:
            steps.append("查询分析：未命中预设纠纷类型关键词，不作纠纷降权")
        if query_region_hit and jurisdiction_boost:
            steps.append(
                f"地域分析：查询命中「{jurisdiction_boost}」语境，可对属地地方法规启用×1.3"
            )
        else:
            steps.append("地域分析：未启用或未命中地域加权语境")
        steps.append(
            f"权重计算：基础相似度{base_sim:.2f} × 纠纷权重{dispute_w} × 地域权重{region_w} × 层级权重{level_w} = {weighted:.2f}"
        )
        steps.append(f"法律层级：识别为「{law_type}」，层级系数×{level_w}")
        steps.append(dispute_note)
        steps.append(region_note)
        analysis["推理过程"] = steps

    return analysis


def _rank_legal_hits(
    raw: Dict[str, Any],
    *,
    q: str,
    effective_dispute: Optional[str],
    inferred: Optional[str],
    jurisdiction_boost: Optional[str],
    query_region_hit: bool,
    similarity_threshold: float,
    top_k: int,
    enable_ai_analysis: bool,
    include_explanation: bool,
) -> List[LegalSearchResult]:
    ids_list = (raw.get("ids") or [[]])[0]
    docs_list = (raw.get("documents") or [[]])[0]
    metas_list = (raw.get("metadatas") or [[]])[0]
    scores_list = (raw.get("scores") or [[]])[0]

    ranked: List[Tuple[float, LegalSearchResult]] = []

    for i, cid in enumerate(ids_list):
        doc_text = docs_list[i] if i < len(docs_list) else ""
        meta = dict(metas_list[i]) if i < len(metas_list) and metas_list[i] else {}
        base_sim = float(scores_list[i]) if i < len(scores_list) else 0.0
        if base_sim < similarity_threshold:
            continue

        law_name = str(meta.get("law_name", "") or "")
        law_type = _metadata_law_type(meta)
        level_w = _LAW_LEVEL_WEIGHT.get(law_type, 1.0)

        d_weight, d_note = _dispute_match_weight(effective_dispute, meta)
        if effective_dispute and d_weight < 0.5:
            continue

        doc_region = _doc_matches_jurisdiction_local(
            law_name, meta, law_type, jurisdiction_boost
        )
        r_weight, r_note = _region_weight(
            query_region_hit, jurisdiction_boost, doc_region, law_type
        )

        weighted = base_sim * d_weight * r_weight * level_w
        article_disp = _format_article_no(meta.get("article_no", ""))
        ai_analysis = _build_ai_analysis(
            base_sim=base_sim,
            dispute_w=d_weight,
            region_w=r_weight,
            level_w=level_w,
            weighted=weighted,
            law_type=law_type,
            effective_dispute=effective_dispute,
            inferred=inferred,
            query=q,
            query_region_hit=query_region_hit,
            jurisdiction_boost=jurisdiction_boost,
            dispute_note=d_note,
            region_note=r_note,
            enable_ai_analysis=enable_ai_analysis,
            include_explanation=include_explanation,
        )

        ranked.append(
            (
                weighted,
                LegalSearchResult(
                    content=doc_text or "",
                    source=law_name or "未知来源",
                    law_type=law_type,
                    similarity=round(min(1.0, max(0.0, base_sim)), 4),
                    article_no=article_disp,
                    chunk_id=str(cid),
                    ai_analysis=ai_analysis,
                ),
            )
        )

    ranked.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in ranked[:top_k]]


def search_legalknowledge(
    query: str,
    vectordb: "LegalVectorDB",
    dispute_type: Optional[str] = None,
    jurisdiction_boost: Optional[str] = "北京",
    enable_ai_analysis: bool = True,
    top_k: int = 10,
    similarity_threshold: float = 0.3,
    include_explanation: bool = True,
) -> List[LegalSearchResult]:
    """
    基于 LegalVectorDB 的智能法律条文检索：语义向量 + 多维度加权 + 可解释输出。

    最终加权得分 = 基础相似度 × 纠纷类型权重 × 地域权重 × 法律层级权重

    Args:
        query: 自然语言查询。
        vectordb: 已初始化的 LegalVectorDB 实例。
        dispute_type: 指定纠纷类型；写入 Chroma ``where`` 过滤 ``dispute_type`` 字段；
            若无命中则自动回退为无 ``where`` 的检索（元数据可能尚未补全）。
        jurisdiction_boost: 地域加权目标，默认「北京」；设为 None 关闭地域×1.3。
        enable_ai_analysis: 是否填充 ai_analysis。
        top_k: 返回条数。
        similarity_threshold: 向量基础相似度下限（与 LegalVectorDB.search 一致）。
        include_explanation: 是否在 ai_analysis 中写入分步推理过程。

    Returns:
        ``LegalSearchResult`` 列表；``similarity`` 为 **基础语义相似度**（0–1），
        排序依据为 ``ai_analysis['最终加权得分']``（可大于 1）。
    """
    if not query or not str(query).strip():
        return []

    q = str(query).strip()
    inferred = _infer_dispute_type(q)
    effective_dispute = (dispute_type or inferred or "").strip() or None

    where: Optional[Dict[str, Any]] = None
    if dispute_type and dispute_type.strip():
        where = {"dispute_type": dispute_type.strip()}

    fetch_n = max(top_k * 5, 30)
    raw = vectordb.search(
        q,
        top_k=fetch_n,
        where=where,
        score_threshold=0.0,
        include=["documents", "metadatas", "distances"],
    )
    if where and not (raw.get("ids") or [[]])[0]:
        raw = vectordb.search(
            q,
            top_k=fetch_n,
            where=None,
            score_threshold=0.0,
            include=["documents", "metadatas", "distances"],
        )

    query_region_hit = _query_mentions_jurisdiction(q, jurisdiction_boost)
    return _rank_legal_hits(
        raw,
        q=q,
        effective_dispute=effective_dispute,
        inferred=inferred,
        jurisdiction_boost=jurisdiction_boost,
        query_region_hit=query_region_hit,
        similarity_threshold=similarity_threshold,
        top_k=top_k,
        enable_ai_analysis=enable_ai_analysis,
        include_explanation=include_explanation,
    )


async def search_legalknowledge_async(
    query: str,
    vectordb: "LegalVectorDB",
    dispute_type: Optional[str] = None,
    jurisdiction_boost: Optional[str] = "北京",
    enable_ai_analysis: bool = True,
    top_k: int = 10,
    similarity_threshold: float = 0.3,
    include_explanation: bool = True,
) -> List[LegalSearchResult]:
    """异步封装：内部调用 ``LegalVectorDB.asearch`` 做向量检索，其余逻辑与同步版一致。"""
    if not query or not str(query).strip():
        return []

    q = str(query).strip()
    inferred = _infer_dispute_type(q)
    effective_dispute = (dispute_type or inferred or "").strip() or None

    where: Optional[Dict[str, Any]] = None
    if dispute_type and dispute_type.strip():
        where = {"dispute_type": dispute_type.strip()}

    fetch_n = max(top_k * 5, 30)
    raw = await vectordb.asearch(
        q,
        top_k=fetch_n,
        where=where,
        score_threshold=0.0,
        include=["documents", "metadatas", "distances"],
    )
    if where and not (raw.get("ids") or [[]])[0]:
        raw = await vectordb.asearch(
            q,
            top_k=fetch_n,
            where=None,
            score_threshold=0.0,
            include=["documents", "metadatas", "distances"],
        )

    query_region_hit = _query_mentions_jurisdiction(q, jurisdiction_boost)
    return _rank_legal_hits(
        raw,
        q=q,
        effective_dispute=effective_dispute,
        inferred=inferred,
        jurisdiction_boost=jurisdiction_boost,
        query_region_hit=query_region_hit,
        similarity_threshold=similarity_threshold,
        top_k=top_k,
        enable_ai_analysis=enable_ai_analysis,
        include_explanation=include_explanation,
    )

def search_with_fallbacks(
    query: str,
    vectordb: "LegalVectorDB",
    dispute_type: Optional[str] = None,
    jurisdiction_boost: Optional[str] = "北京",
    top_k: int = 5,
    similarity_threshold: float = 0.3,
) -> List[LegalSearchResult]:
    """
    多级回退检索：
    1. 按 dispute_type + jurisdiction_boost（如果提供）
    2. 若结果为空，去掉 jurisdiction_boost
    3. 若仍为空，去掉 dispute_type
    """
    # 第一级：完整条件
    results = search_legalknowledge(
        query=query,
        vectordb=vectordb,
        dispute_type=dispute_type,
        jurisdiction_boost=jurisdiction_boost,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    if results:
        return results

    # 第二级：去掉地域加权
    results = search_legalknowledge(
        query=query,
        vectordb=vectordb,
        dispute_type=dispute_type,
        jurisdiction_boost=None,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    if results:
        return results

    # 第三级：去掉纠纷类型
    results = search_legalknowledge(
        query=query,
        vectordb=vectordb,
        dispute_type=None,
        jurisdiction_boost=None,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    return results