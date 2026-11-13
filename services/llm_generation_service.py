import json
import re
from typing import Any

import httpx

from api import settings
from api.models import CaseReference, EmotionGuidance, LegalReference


class LLMGenerationError(RuntimeError):
    pass


def _build_prompt(
    *,
    description: str,
    dispute_type: str,
    risk_level: str,
    emotion_guidance: EmotionGuidance,
    legal_basis: list[LegalReference],
    case_references: list[CaseReference],
) -> str:
    legal_context = [
        {
            "title": item.title,
            "article": item.article,
            "excerpt": item.excerpt,
            "region": item.region,
            "source_url": item.source_url,
        }
        for item in legal_basis
    ]
    case_context = [
        {
            "title": item.title,
            "summary": item.summary,
            "handling_points": item.handling_points,
            "region": item.region,
            "source_url": item.source_url,
        }
        for item in case_references
    ]
    payload = {
        "case_description": description,
        "dispute_type": dispute_type,
        "risk_level": risk_level,
        "emotion_guidance": emotion_guidance.model_dump(),
        "legal_basis": legal_context,
        "case_references": case_context,
        "task": {
            "goal": "生成用于基层调解的结构化建议",
            "requirements": [
                "只能基于提供的法规和案例生成，不得编造法律依据",
                "输出 JSON，包含 summary, steps, confidence, needs_human_review",
                "steps 为 3-5 条，尽量可执行、口吻中性",
                "若证据不足，confidence 应降低并明确需要人工复核",
            ],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _strip_wrappers(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_json_text(text: str) -> str:
    cleaned = _strip_wrappers(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _parse_json_payload(text: str) -> dict[str, Any]:
    candidate = _extract_json_text(text)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMGenerationError(f"模型返回内容不是合法 JSON: {candidate[:200]}") from exc
    if not isinstance(data, dict):
        raise LLMGenerationError("模型返回内容格式异常")
    return data


def _generate_with_ollama(prompt: str) -> dict[str, Any]:
    payload = {
        "model": settings.GENERATION_MODEL,
        "stream": False,
        "format": "json",
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个严格遵守证据约束的法律调解辅助系统。"
                    "只能根据输入中的法律依据和案例摘要生成内容，禁止编造法规。"
                    "必须仅输出 JSON，不要输出 markdown，不要输出解释。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "options": {
            "temperature": 0.2,
            "top_p": 0.9,
        },
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    try:
        response = httpx.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMGenerationError(f"Ollama 调用失败: {exc}") from exc
    body = response.json()
    text = ((body.get("message") or {}).get("content") or "").strip()
    if not text:
        raise LLMGenerationError("Ollama 未返回有效内容")
    return _parse_json_payload(text)


def _generate_with_openai(prompt: str) -> dict[str, Any]:
    if not settings.has_openai_credentials():
        raise LLMGenerationError("OpenAI LLM 未启用或未配置密钥")

    from openai import OpenAI

    client_kwargs: dict[str, Any] = {"api_key": settings.OPENAI_API_KEY}
    if settings.OPENAI_BASE_URL:
        client_kwargs["base_url"] = settings.OPENAI_BASE_URL
    client = OpenAI(**client_kwargs)

    response = client.responses.create(
        model=settings.GENERATION_MODEL,
        instructions=(
            "你是一个严格遵守证据约束的法律调解辅助系统。"
            "只能根据输入中的法律依据和案例摘要生成内容，禁止编造法规。"
            "必须仅输出 JSON，不要输出 markdown。"
        ),
        input=prompt,
    )
    text = response.output_text.strip()
    if not text:
        raise LLMGenerationError("模型未返回有效内容")
    return _parse_json_payload(text)


def _generate_with_aliyun(prompt: str) -> dict[str, Any]:
    """阿里云百炼（DashScope）OpenAI 兼容接口生成。

    补充 aliyun_llm_key 调用方式（agent_role 目标）。
    DashScope 兼容模式支持 chat.completions，故使用 chat.completions.create。
    """
    if not settings.has_aliyun_credentials():
        raise LLMGenerationError("阿里云 LLM 未启用或未配置密钥")

    from openai import OpenAI

    client = OpenAI(api_key=settings.ALIYUN_LLM_KEY, base_url=settings.ALIYUN_BASE_URL)
    response = client.chat.completions.create(
        model=settings.ALIYUN_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个严格遵守证据约束的法律调解辅助系统。"
                    "只能根据输入中的法律依据和案例摘要生成内容，禁止编造法规。"
                    "必须仅输出 JSON，不要输出 markdown。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise LLMGenerationError("模型未返回有效内容")
    return _parse_json_payload(text)


def generate_with_llm(
    *,
    description: str,
    dispute_type: str,
    risk_level: str,
    emotion_guidance: EmotionGuidance,
    legal_basis: list[LegalReference],
    case_references: list[CaseReference],
) -> dict[str, Any]:
    if not settings.llm_generation_enabled():
        raise LLMGenerationError("LLM 未启用或未完成配置")

    prompt = _build_prompt(
        description=description,
        dispute_type=dispute_type,
        risk_level=risk_level,
        emotion_guidance=emotion_guidance,
        legal_basis=legal_basis,
        case_references=case_references,
    )

    if settings.GENERATION_PROVIDER == "ollama":
        return _generate_with_ollama(prompt)
    if settings.GENERATION_PROVIDER == "openai":
        return _generate_with_openai(prompt)
    if settings.GENERATION_PROVIDER == "aliyun":
        return _generate_with_aliyun(prompt)
    raise LLMGenerationError(f"不支持的 GENERATION_PROVIDER: {settings.GENERATION_PROVIDER}")
