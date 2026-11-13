"""调解主链路编排（合并后唯一生成路径）。

修复 P3：不再调用旧 rag/ 单库引擎，改为
  双知识库检索(repositories) -> 结构化 LLM 生成(services) -> 规则拼装回退(core)。
模型/provider/开关全部由 api.settings 驱动，删除调试文件写入与噪声 print。
"""
import asyncio
import logging
from uuid import uuid4

from api.models import MediationRequest, MediationResponse
from core.dispute_recognition import recognize_dispute
from core.emotion_guidance import build_emotion_guidance
from core.decision_support import build_summary, build_steps
from services.legal_kb_service import search_dual_knowledge, get_runtime_profile
from services.llm_generation_service import generate_with_llm, LLMGenerationError

logger = logging.getLogger(__name__)


async def generate_mediation(payload: MediationRequest) -> MediationResponse:
    # 1. 纠纷识别与情绪引导
    recognition = recognize_dispute(payload.description)
    emotion_guidance = build_emotion_guidance(payload.description)
    runtime = get_runtime_profile()

    # 2. 双知识库检索（法规 + 案例），地域/纠纷类型过滤
    legal_basis, case_references = search_dual_knowledge(
        dispute_type=recognition.dispute_type,
        query=payload.description,
        region=payload.preferred_region,
    )

    summary = None
    steps: list[str] = []
    confidence = recognition.confidence
    needs_human_review = True
    source = "system"

    # 3. 结构化 LLM 生成（阻塞调用放入线程，避免阻塞事件循环）；失败回退规则拼装
    try:
        generated = await asyncio.to_thread(
            generate_with_llm,
            description=payload.description,
            dispute_type=recognition.dispute_type,
            risk_level=recognition.risk_level,
            emotion_guidance=emotion_guidance,
            legal_basis=legal_basis,
            case_references=case_references,
        )
        summary = generated.get("summary")
        steps = generated.get("steps") or []
        confidence = float(generated.get("confidence", confidence))
        needs_human_review = bool(generated.get("needs_human_review", True))
        source = "live"
    except LLMGenerationError as exc:
        logger.warning("LLM 未启用或生成失败，回退规则拼装: %s", exc)
        runtime.notes.append("LLM 未启用或生成失败，已回退到规则拼装结果。")
    except Exception:
        logger.exception("LLM 生成异常，回退规则拼装")
        runtime.notes.append("LLM 生成异常，已回退到规则拼装结果。")

    # 4. 规则回退：LLM 未给出有效摘要/步骤时，用检索证据拼装
    if not summary or not steps:
        summary = build_summary(
            recognition.dispute_type, recognition.matched_keywords, legal_basis, case_references
        )
        steps = build_steps(recognition.dispute_type, legal_basis, case_references)
        source = "system"

    return MediationResponse(
        case_id=str(uuid4()),
        dispute_type=recognition.dispute_type,
        legal_basis=legal_basis,
        case_references=case_references,
        steps=steps,
        needs_human_review=needs_human_review,
        source=source,
        summary=summary,
        matched_keywords=recognition.matched_keywords,
        risk_level=recognition.risk_level,
        confidence=confidence,
        emotion_guidance=emotion_guidance,
        runtime=runtime,
    )