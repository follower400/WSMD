from api.models import EmotionGuidance

EMOTION_SIGNALS = {
    "tense": ["多次沟通未果", "争执", "拖欠", "影响休息", "冲突", "投诉"],
    "escalated": ["家暴", "威胁", "报警", "人身安全", "激烈", "殴打"],
}


def build_emotion_guidance(description: str) -> EmotionGuidance:
    signals: list[str] = []
    level = "stable"
    for keyword in EMOTION_SIGNALS["escalated"]:
        if keyword in description:
            signals.append(keyword)
            level = "escalated"
    if level != "escalated":
        for keyword in EMOTION_SIGNALS["tense"]:
            if keyword in description:
                signals.append(keyword)
                level = "tense"

    if level == "escalated":
        tips = [
            "优先确认是否存在人身安全风险，必要时建议立即转入专业处置渠道。",
            "调解时使用中性措辞，避免刺激性追问。",
            "在安全前提下分开沟通，降低现场对抗。",
        ]
    elif level == "tense":
        tips = [
            "先让双方分别陈述，避免抢话和情绪叠加。",
            "优先固定事实，再讨论责任与方案。",
            "使用可执行、可量化的约定替代笼统承诺。",
        ]
    else:
        tips = [
            "保持中性表达和事实导向。",
            "围绕争议焦点逐项确认，避免扩散话题。",
        ]

    return EmotionGuidance(level=level, detected_signals=signals, mediator_tips=tips)
