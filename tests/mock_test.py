import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def assert_ok(response, label: str) -> None:
    if response.status_code != 200:
        raise AssertionError(f"{label} 失败: {response.status_code} {response.text}")


def main() -> int:
    health = client.get("/health")
    assert_ok(health, "/health")
    health_json = health.json()
    print("[OK] /health", health_json)
    if not health_json.get("knowledge_base_loaded"):
        raise AssertionError("知识库未成功加载")

    runtime = client.get("/system/runtime-profile")
    assert_ok(runtime, "/system/runtime-profile")
    runtime_json = runtime.json()
    print("[OK] /system/runtime-profile", runtime_json)
    if runtime_json["counts"]["legal_items"] < 1 or runtime_json["counts"]["case_items"] < 1:
        raise AssertionError("知识库计数异常")
    if runtime_json["runtime"]["generation_mode"] not in {"rule_based", "rag_llm"}:
        raise AssertionError("generation_mode 非法")

    cases = client.get("/mock/cases")
    assert_ok(cases, "/mock/cases")
    cases_json = cases.json()
    print("[OK] /mock/cases", cases_json)
    first_id = cases_json["cases"][0]["id"]

    plan = client.get(f"/mock/mediation/{first_id}")
    assert_ok(plan, "/mock/mediation/{case_id}")
    plan_json = plan.json()
    print("[OK] /mock/mediation/{case_id}", plan_json)
    if not plan_json.get("case_references"):
        raise AssertionError("mock 调解结果缺少相似案例")

    payload = {
        "description": "邻居装修噪音太大，影响休息，多次沟通未果",
        "party_a": "张先生",
        "party_b": "王女士",
        "preferred_region": "北京",
    }
    mediate = client.post("/mediate", json=payload)
    assert_ok(mediate, "/mediate")
    mediate_json = mediate.json()
    print("[OK] /mediate", mediate_json)
    if mediate_json.get("dispute_type") != "邻里纠纷":
        raise AssertionError("/mediate 未按预期识别为邻里纠纷")
    if not mediate_json.get("legal_basis"):
        raise AssertionError("/mediate 缺少法律依据")
    if not mediate_json.get("emotion_guidance"):
        raise AssertionError("/mediate 缺少情绪引导")

    knowledge = client.get("/knowledge/search", params={"q": "噪音", "dispute_type": "邻里纠纷", "region": "北京"})
    assert_ok(knowledge, "/knowledge/search")
    knowledge_json = knowledge.json()
    print("[OK] /knowledge/search", knowledge_json)
    if knowledge_json.get("total_legal", 0) < 1:
        raise AssertionError("/knowledge/search 未返回法规结果")

    not_found = client.get("/mock/mediation/not-exist")
    if not_found.status_code != 404:
        raise AssertionError("/mock/mediation 缺少 404 校验")
    print("[OK] /mock/mediation/not-exist", not_found.json())

    invalid = client.post("/mediate", json={"description": "太短"})
    if invalid.status_code != 422:
        raise AssertionError("/mediate 缺少请求体验证")
    print("[OK] /mediate invalid payload", invalid.json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
