"""API 路由集中定义。

修复 P4：
- 合并重复 /health 为单一真实状态（经 legal_kb_service 判断知识库/计数）；
- /system/runtime-profile 使用真实运行画像与双库计数，去除写死值；
- /knowledge/search 使用双知识库检索并应用 dispute_type/region 过滤；
- 注册 POST /system/build-real-kb（前端建库动作依赖）。
"""
from fastapi import APIRouter, HTTPException

from api.models import (
    MediationRequest,
    MediationResponse,
    KnowledgeSearchResponse,
    RuntimeProfileResponse,
    IngestBuildRequest,
    IngestBuildResponse,
)
from api.settings import APP_VERSION
from data.mock_data_generator import get_mock_cases, get_mock_mediation
from services.mediation_service import generate_mediation
from services.legal_kb_service import (
    search_dual_knowledge,
    get_runtime_profile,
    has_knowledge_bases,
)
from repositories.knowledge_repository import knowledge_counts

router = APIRouter()


# ========== 健康检查（单一真实状态）==========
@router.get("/health")
async def health():
    runtime = get_runtime_profile()
    return {
        "status": "ok",
        "service": "wisdom-mediator",
        "version": APP_VERSION,
        "knowledge_base_loaded": has_knowledge_bases(),
        "retrieval_mode": runtime.retrieval_mode,
        "database_connected": runtime.database_connected,
        "counts": knowledge_counts(),
    }


# ========== 案例接口 ==========
@router.get("/cases")
async def get_cases():
    """预设案例列表（前端使用）"""
    return {"cases": get_mock_cases()}


@router.get("/mock/cases")
async def read_mock_cases():
    return {"cases": get_mock_cases()}


@router.get("/mock/mediation/{case_id}")
async def read_mock_mediation(case_id: str):
    result = get_mock_mediation(case_id)
    if not result:
        raise HTTPException(status_code=404, detail="未找到案例")
    return result


# ========== 调解生成 ==========
@router.post("/mediation/generate", response_model=MediationResponse)
async def create_mediation(request: MediationRequest):
    return await generate_mediation(request)


# 兼容旧版 /mediate 路径
@router.post("/mediate", response_model=MediationResponse)
async def create_mediation_legacy(payload: MediationRequest):
    return await generate_mediation(payload)


# ========== 知识检索（双库 + 过滤）==========
@router.get("/knowledge/search", response_model=KnowledgeSearchResponse)
async def knowledge_search(
    q: str = "",
    dispute_type: str | None = None,
    region: str | None = None,
    legal_limit: int = 5,
    case_limit: int = 3,
):
    legal_items, case_items = search_dual_knowledge(
        dispute_type=dispute_type,
        query=q,
        region=region,
        legal_limit=legal_limit,
        case_limit=case_limit,
    )
    return KnowledgeSearchResponse(
        legal_items=legal_items,
        case_items=case_items,
        total_legal=len(legal_items),
        total_cases=len(case_items),
        runtime=get_runtime_profile(),
    )


# ========== 运行架构画像 ==========
@router.get("/system/runtime-profile", response_model=RuntimeProfileResponse)
async def runtime_profile():
    return RuntimeProfileResponse(runtime=get_runtime_profile(), counts=knowledge_counts())


# ========== 真实知识库建库 ==========
@router.post("/system/build-real-kb", response_model=IngestBuildResponse)
def build_real_kb(request: IngestBuildRequest):
    # 同步路由：FastAPI 自动放入线程池，避免阻塞事件循环（建库会加载 embedding 模型）
    from services.ingest_service import build_real_knowledge_base

    return build_real_knowledge_base(
        laws_path=request.laws_path,
        cases_path=request.cases_path,
        rebuild=request.rebuild,
    )