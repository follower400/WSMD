from api.models import CaseItem, CaseReference, EmotionGuidance, LegalReference, MediationResponse
from services.legal_kb_service import get_runtime_profile

MOCK_CASES = [
    CaseItem(
        id="case-001",
        description="邻居装修噪音太大，晚上十点后仍在施工，已经持续三天，影响休息。",
        dispute_type="邻里纠纷",
        party_a="张先生",
        party_b="王女士",
        date="2026-04-20",
        status="待处理",
    ),
    CaseItem(
        id="case-002",
        description="物业称业主拖欠物业费，双方因服务质量发生争执。",
        dispute_type="物业纠纷",
        party_a="李女士",
        party_b="某物业公司",
        date="2026-04-18",
        status="待处理",
    ),
    CaseItem(
        id="case-003",
        description="楼上住户夜间持续拖动桌椅，影响楼下休息，多次沟通未果。",
        dispute_type="邻里纠纷",
        party_a="赵先生",
        party_b="孙女士",
        date="2026-04-16",
        status="待沟通",
    ),
]

runtime = get_runtime_profile()

MOCK_MEDIATIONS = {
    "case-001": MediationResponse(
        case_id="case-001",
        dispute_type="邻里纠纷",
        legal_basis=[
            LegalReference(
                id="law-neighbor-001",
                title="中华人民共和国民法典",
                article="第二百八十八条",
                excerpt="不动产的相邻权利人应当按照有利生产、方便生活、团结互助、公平合理的原则，正确处理相邻关系。",
                source_level="national",
                dispute_type="邻里纠纷",
                region="全国",
                keywords=["邻居", "相邻关系", "噪音", "装修"],
                score=9.0,
                matched_tokens=["装修", "噪音"],
            ),
            LegalReference(
                id="law-neighbor-002",
                title="中华人民共和国噪声污染防治法",
                article="相关条款",
                excerpt="对噪声敏感建筑物集中区域内，禁止夜间进行产生噪声污染的建筑施工作业等活动。",
                source_level="national",
                dispute_type="邻里纠纷",
                region="全国",
                keywords=["夜间", "施工", "扰民", "噪音"],
                score=8.5,
                matched_tokens=["夜间", "施工", "噪音"],
            ),
        ],
        case_references=[
            CaseReference(
                id="case-kb-001",
                title="夜间装修噪音纠纷调解案例",
                summary="装修方夜间施工引发邻里矛盾，最终通过限定施工时段和书面承诺解决。",
                dispute_type="邻里纠纷",
                region="北京",
                keywords=["装修", "噪音", "夜间"],
                handling_points=["核实施工时段", "约定夜间静音规则", "引入物业监督"],
                score=7.8,
                matched_tokens=["装修", "噪音", "夜间"],
            )
        ],
        steps=[
            "第一步：核实施工时间、频率与实际影响。",
            "第二步：了解双方诉求，明确矛盾焦点。",
            "第三步：建议施工方在合理时段内作业并提前告知。",
            "第四步：协商补救措施与后续监督方式。",
        ],
        needs_human_review=True,
        source="mock",
        summary="该案例适合先从噪音时段和影响程度入手，再协商施工限制。",
        matched_keywords=["装修", "噪音", "施工"],
        risk_level="medium",
        confidence=0.82,
        emotion_guidance=EmotionGuidance(level="tense", detected_signals=["影响休息"], mediator_tips=["先让双方分别陈述，避免抢话和情绪叠加。", "优先固定事实，再讨论责任与方案。", "使用可执行、可量化的约定替代笼统承诺。"]),
        runtime=runtime,
    ),
    "case-002": MediationResponse(
        case_id="case-002",
        dispute_type="物业纠纷",
        legal_basis=[
            LegalReference(
                id="law-property-001",
                title="中华人民共和国民法典",
                article="物业服务合同相关条款",
                excerpt="物业服务人应当按照约定和物业的使用性质，妥善维修、养护、清洁、绿化和经营管理物业服务区域内的业主共有部分。",
                source_level="national",
                dispute_type="物业纠纷",
                region="全国",
                keywords=["物业", "物业费", "服务质量"],
                score=8.7,
                matched_tokens=["物业", "服务质量"],
            ),
            LegalReference(
                id="law-property-002",
                title="北京市物业管理条例",
                article="相关条款",
                excerpt="物业服务活动应当接受业主监督，物业服务收费应当公开透明。",
                source_level="local",
                dispute_type="物业纠纷",
                region="北京",
                keywords=["物业", "收费", "服务质量"],
                score=8.2,
                matched_tokens=["物业", "收费"],
            ),
        ],
        case_references=[
            CaseReference(
                id="case-kb-002",
                title="物业费与服务质量争议调解案例",
                summary="业主认为物业服务不到位，物业认为费用拖欠，最终通过公开服务清单和分期支付方案达成一致。",
                dispute_type="物业纠纷",
                region="北京",
                keywords=["物业", "物业费", "服务质量"],
                handling_points=["区分收费争议和服务争议", "调阅合同和服务记录", "围绕整改与支付计划协商"],
                score=7.5,
                matched_tokens=["物业", "物业费", "服务质量"],
            )
        ],
        steps=[
            "第一步：核对物业费标准、服务内容及收费依据。",
            "第二步：梳理争议点，区分费用问题与服务质量问题。",
            "第三步：协商服务整改与分阶段支付安排。",
            "第四步：形成书面记录并明确后续处理时限。",
        ],
        needs_human_review=True,
        source="mock",
        summary="该案例应先明确收费依据，再同步评估物业服务是否履约。",
        matched_keywords=["物业", "物业费", "服务质量"],
        risk_level="medium",
        confidence=0.8,
        emotion_guidance=EmotionGuidance(level="tense", detected_signals=["争执", "拖欠"], mediator_tips=["先让双方分别陈述，避免抢话和情绪叠加。", "优先固定事实，再讨论责任与方案。", "使用可执行、可量化的约定替代笼统承诺。"]),
        runtime=runtime,
    ),
    "case-003": MediationResponse(
        case_id="case-003",
        dispute_type="邻里纠纷",
        legal_basis=[
            LegalReference(
                id="law-neighbor-001",
                title="中华人民共和国民法典",
                article="第二百八十八条",
                excerpt="不动产的相邻权利人应当按照有利生产、方便生活、团结互助、公平合理的原则，正确处理相邻关系。",
                source_level="national",
                dispute_type="邻里纠纷",
                region="全国",
                keywords=["邻居", "相邻关系", "扰民"],
                score=7.9,
                matched_tokens=["楼上", "楼下", "扰民"],
            )
        ],
        case_references=[
            CaseReference(
                id="case-kb-001",
                title="夜间装修噪音纠纷调解案例",
                summary="装修方夜间施工引发邻里矛盾，最终通过限定施工时段和书面承诺解决。",
                dispute_type="邻里纠纷",
                region="北京",
                keywords=["邻里", "夜间", "噪音"],
                handling_points=["确认夜间扰民频次", "设置静音时段约定", "社区或物业跟进监督"],
                score=6.9,
                matched_tokens=["夜间", "楼上", "楼下"],
            )
        ],
        steps=[
            "第一步：确认夜间扰民的具体时段和频次。",
            "第二步：听取双方陈述并核实历史沟通情况。",
            "第三步：提出夜间安静时段约定和提醒机制。",
            "第四步：必要时引入物业或社区协助跟进。",
        ],
        needs_human_review=True,
        source="mock",
        summary="该案例更适合通过行为约定和社区协调来降温处理。",
        matched_keywords=["楼上", "楼下", "拖动桌椅"],
        risk_level="medium",
        confidence=0.78,
        emotion_guidance=EmotionGuidance(level="tense", detected_signals=["多次沟通未果", "影响休息"], mediator_tips=["先让双方分别陈述，避免抢话和情绪叠加。", "优先固定事实，再讨论责任与方案。", "使用可执行、可量化的约定替代笼统承诺。"]),
        runtime=runtime,
    ),
}


def get_mock_cases() -> list[CaseItem]:
    return [item.model_copy(deep=True) for item in MOCK_CASES]


def get_mock_case_by_id(case_id: str) -> CaseItem | None:
    matched = next((item for item in MOCK_CASES if item.id == case_id), None)
    return matched.model_copy(deep=True) if matched else None


def get_mock_mediation(case_id: str) -> MediationResponse | None:
    matched = MOCK_MEDIATIONS.get(case_id)
    return matched.model_copy(deep=True) if matched else None
