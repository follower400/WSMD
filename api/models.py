from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator,model_validator

from api.settings import (
    APP_VERSION,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    KNOWLEDGE_BACKEND,
    KNOWLEDGE_RETRIEVAL_MODE,
    VECTOR_BACKEND,
)

ResultSource = Literal["mock", "live", "system"]
LegalSourceLevel = Literal["national", "local", "case", "community"]
RiskLevel = Literal["low", "medium", "high"]
EmotionLevel = Literal["stable", "tense", "escalated"]
GenerationMode = Literal["rule_based", "rag_llm"]


class HealthResponse(BaseModel):
    status: str
    service: str = "wisdom-mediator"
    version: str = APP_VERSION
    knowledge_base_loaded: bool = True
    retrieval_mode: str = KNOWLEDGE_RETRIEVAL_MODE
    database_connected: bool = False


class LegalReference(BaseModel):
    id: str
    title: str
    article: str
    excerpt: str
    source_level: LegalSourceLevel
    dispute_type: Optional[str] = None
    region: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    score: float = 0.0
    matched_tokens: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    effective_status: Optional[str] = None


class CaseReference(BaseModel):
    id: str
    title: str
    summary: str
    dispute_type: str
    region: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    handling_points: list[str] = Field(default_factory=list)
    score: float = 0.0
    matched_tokens: list[str] = Field(default_factory=list)
    source_url: Optional[str] = None


class EmotionGuidance(BaseModel):
    level: EmotionLevel = "stable"
    detected_signals: list[str] = Field(default_factory=list)
    mediator_tips: list[str] = Field(default_factory=list)


class RuntimeProfile(BaseModel):
    knowledge_backend: str = KNOWLEDGE_BACKEND
    vector_backend: str = VECTOR_BACKEND
    retrieval_mode: str = KNOWLEDGE_RETRIEVAL_MODE
    database_connected: bool = False
    supports_true_vector_search: bool = False
    supports_rag_generation: bool = False
    generation_model: Optional[str] = GENERATION_MODEL
    embedding_model: Optional[str] = EMBEDDING_MODEL
    generation_mode: GenerationMode = "rule_based"
    notes: list[str] = Field(default_factory=list)


class HealthProfileResponse(BaseModel):
    status: str = "ok"
    runtime: RuntimeProfile


class CaseItem(BaseModel):
    id: str
    description: str
    dispute_type: Optional[str] = None
    party_a: Optional[str] = None
    party_b: Optional[str] = None
    date: Optional[str] = None
    status: Optional[str] = None


class MockCasesResponse(BaseModel):
    cases: list[CaseItem]


class MediationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    description: str = Field(..., min_length=5, description="案件描述，至少 5 个字符")
    party_a: Optional[str] = Field(default=None, max_length=50)
    party_b: Optional[str] = Field(default=None, max_length=50)
    preferred_region: Optional[str] = Field(default=None, max_length=20)

    @field_validator("description", check_fields=False)
    @classmethod
    def normalize_description(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 5:
            raise ValueError("案件描述不能为空，且至少输入 5 个字符。")
        return normalized

    @field_validator("party_a", "party_b", "preferred_region")
    @classmethod
    def empty_string_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode='before')
    @classmethod
    def check_case_description(cls, values):
        # 这个方法是关键：处理来自前端的 case_description 字段
        if isinstance(values, dict):
            # 如果请求里有 case_description 但没有 description
            if 'case_description' in values and 'description' not in values:
                # 就把它的值赋给 description
                values['description'] = values['case_description']
        return values


class MediationResponse(BaseModel):
    case_id: str
    dispute_type: str
    legal_basis: list[LegalReference]
    case_references: list[CaseReference] = Field(default_factory=list)
    steps: list[str]
    needs_human_review: bool
    source: ResultSource = "system"
    summary: Optional[str] = None
    matched_keywords: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = "medium"
    confidence: float = 0.0
    emotion_guidance: EmotionGuidance = Field(default_factory=EmotionGuidance)
    runtime: RuntimeProfile = Field(default_factory=RuntimeProfile)


class KnowledgeSearchResponse(BaseModel):
    legal_items: list[LegalReference]
    case_items: list[CaseReference]
    total_legal: int
    total_cases: int
    runtime: RuntimeProfile


class RuntimeProfileResponse(BaseModel):
    runtime: RuntimeProfile
    counts: dict[str, int]


class IngestBuildRequest(BaseModel):
    laws_path: Optional[str] = None
    cases_path: Optional[str] = None
    rebuild: bool = False


class IngestBuildResponse(BaseModel):
    status: str
    legal_chunks: int
    case_chunks: int
    law_collection: str
    case_collection: str
    runtime: RuntimeProfile
