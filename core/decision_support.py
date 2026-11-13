from api.models import CaseReference, LegalReference


def build_steps(dispute_type: str, legal_basis: list[LegalReference], case_references: list[CaseReference]) -> list[str]:
    law_hint = legal_basis[0].title if legal_basis else "相关法律规范"
    case_hint = case_references[0].title if case_references else "相似案例"

    if dispute_type == "邻里纠纷":
        return [
            "第一步：核实噪音、装修或公共活动发生的时间、频次和持续时长。",
            "第二步：固定双方既往沟通记录，明确影响睡眠、通行或安宁的事实。",
            f"第三步：结合《{law_hint}》中的相邻关系或噪声管理依据，提出可执行的限时、降噪、调整场地建议。",
            f"第四步：参考“{case_hint}”中的处理经验，必要时引入社区、物业或居委会共同监督。",
        ]
    if dispute_type == "物业纠纷":
        return [
            "第一步：核对物业服务合同、收费依据和具体服务内容。",
            "第二步：区分收费争议、服务质量争议与公共设施维护争议。",
            f"第三步：结合《{law_hint}》与检索到的案例，围绕整改措施、收费依据和分期安排组织协商。",
            "第四步：形成书面记录并明确责任主体、时间节点和复核方式。",
        ]
    if dispute_type == "家庭纠纷":
        return [
            "第一步：梳理家庭成员关系、争议焦点和时间线。",
            "第二步：识别是否存在家暴、人身安全或财产转移等高风险因素。",
            f"第三步：结合《{law_hint}》围绕赡养、抚养、居住安排或财产问题进行分项沟通。",
            "第四步：必要时建议转入更专业的法律援助、妇联、社工或公安处置渠道。",
        ]
    return [
        "第一步：了解案件基本事实与时间线。",
        "第二步：识别双方核心诉求与主要分歧。",
        f"第三步：综合 {len(legal_basis)} 条法条依据与 {len(case_references)} 个相似案例提出中性调解建议。",
        "第四步：提示调解员结合现场情况进行人工复核。",
    ]


def build_summary(dispute_type: str, matched_keywords: list[str], legal_basis: list[LegalReference], case_references: list[CaseReference]) -> str:
    keyword_text = "、".join(matched_keywords) if matched_keywords else "未识别到明确关键词"
    law_titles = "、".join(sorted({item.title for item in legal_basis})) if legal_basis else "通用法律规范"
    case_titles = "、".join(sorted({item.title for item in case_references})) if case_references else "暂无相似案例"
    return f"系统识别为{dispute_type}，命中关键词：{keyword_text}；优先参考法规：{law_titles}；相似案例：{case_titles}。"
