from dataclasses import dataclass


@dataclass
class DisputeRecognitionResult:
    dispute_type: str
    matched_keywords: list[str]
    confidence: float
    risk_level: str


SYNONYM_MAP: dict[str, list[str]] = {
    "广场舞": ["噪音", "扰民", "公共活动"],
    "睡眠": ["休息", "夜间"],
    "晚上十点": ["夜间"],
    "深夜": ["夜间"],
    "喇叭": ["噪音"],
    "音响": ["噪音"],
    "出卖婴儿": ["出卖", "婴儿", "未成年人", "监护", "撤销监护资格"],
    "卖婴儿": ["出卖", "婴儿", "未成年人", "监护"],
    "监护资格": ["监护", "监护人"],
    "撤销监护资格": ["撤销", "监护", "监护人", "资格"],
    "指定监护人": ["监护", "监护人", "民政局"],
    "民政局": ["民政部门", "监护"],
    "未成年人": ["监护", "未成年子女"],
    "婴儿": ["未成年人", "监护"],
    "头盔": ["安全头盔", "交通事故"],
    "无接触事故": ["交通事故", "安全距离"],
    "专项维修资金": ["物业", "维修", "物业服务合同"],
}

DISPUTE_PATTERNS: dict[str, dict[str, object]] = {
    "监护纠纷": {
        "keywords": [
            "监护",
            "监护人",
            "监护资格",
            "撤销监护资格",
            "指定监护人",
            "民政局",
            "民政部门",
            "未成年人",
            "未成年子女",
            "婴儿",
            "出卖",
            "出卖婴儿",
            "最有利于未成年人",
        ],
        "risk_level": "high",
    },
    "邻里纠纷": {
        "keywords": [
            "装修", "噪音", "楼上", "楼下", "邻居", "扰民", "拖动桌椅", "夜间",
            "广场舞", "跳舞", "睡眠", "音响", "喇叭", "唱歌", "施工", "休息",
        ],
        "risk_level": "medium",
    },
    "物业纠纷": {
        "keywords": [
            "物业", "物业费", "服务质量", "停车费", "停车位", "收费",
            "保安", "维修", "电梯", "业主委员会", "专项维修资金", "物业服务合同",
        ],
        "risk_level": "medium",
    },
    "交通事故纠纷": {
        "keywords": [
            "交通事故", "机动车", "摩托车", "汽车", "无接触事故",
            "安全距离", "头盔", "右转", "刹车", "侵权责任",
        ],
        "risk_level": "high",
    },
    "家庭纠纷": {
        "keywords": ["夫妻", "家庭", "财产", "赡养", "抚养", "家暴", "离婚", "老人", "子女"],
        "risk_level": "high",
    },
    "合同纠纷": {
        "keywords": ["合同", "租赁", "押金", "违约", "履行", "退款", "租金", "协议"],
        "risk_level": "medium",
    },
}


FALLBACK = DisputeRecognitionResult(
    dispute_type="一般民事纠纷",
    matched_keywords=[],
    confidence=0.35,
    risk_level="medium",
)


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    for phrase, extra_tokens in SYNONYM_MAP.items():
        if phrase in lowered:
            lowered += " " + " ".join(extra_tokens)
    return lowered


def recognize_dispute(description: str) -> DisputeRecognitionResult:
    lowered = _normalize_text(description)
    best: DisputeRecognitionResult | None = None

    for dispute_type, config in DISPUTE_PATTERNS.items():
        keywords = [kw for kw in config["keywords"] if kw.lower() in lowered]
        if not keywords:
            continue

        unique_keywords = list(dict.fromkeys(keywords))

        # 监护纠纷给一点额外权重，避免被其他类别抢走
        base = 0.45
        bonus = len(unique_keywords) * 0.08
        if dispute_type == "监护纠纷":
            bonus += 0.08
        confidence = min(base + bonus, 0.95)

        candidate = DisputeRecognitionResult(
            dispute_type=dispute_type,
            matched_keywords=unique_keywords,
            confidence=round(confidence, 2),
            risk_level=str(config["risk_level"]),
        )

        if best is None or candidate.confidence > best.confidence:
            best = candidate

    return best or FALLBACK