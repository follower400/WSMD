"""应用入口：仅负责创建 FastAPI 应用、注册路由与 CORS。

修复 P2/P3：移除导入即 eager 初始化 LegalVectorDB（会触发 embedding 模型下载，
阻碍离线跑通）；向量库改为按需懒加载。所有业务路由集中在 api/routes.py。
"""
import os

# HuggingFace 镜像（便于国内下载 embedding 模型）；不覆盖用户已设置的值
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from api.routes import router
from api.settings import APP_DESCRIPTION, APP_NAME, APP_VERSION, get_allowed_origins

app = FastAPI(
    title=APP_NAME,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

app.include_router(router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/docs")