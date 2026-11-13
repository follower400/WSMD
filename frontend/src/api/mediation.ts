import { API_BASE } from "@/lib/config";
import type {
  CaseItem,
  HealthResponse,
  IngestBuildResponse,
  KnowledgeSearchResponse,
  MediationRequest,
  MediationResponse,
  RuntimeProfileResponse,
} from "@/types/mediation";

export async function getPresetCases(): Promise<{ cases: CaseItem[] }> {
  const response = await fetch(`${API_BASE}/cases`);
  return response.json();
}

async function parseJson<T>(response: Response): Promise<T> {
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    if (isJson && payload && typeof payload === "object" && "detail" in payload) {
      const detail = (payload as Record<string, unknown>).detail;
      const message = typeof detail === "string" ? detail : JSON.stringify(detail);
      throw new Error(`${response.status} ${message}`.trim());
    }
    throw new Error(`${response.status} ${String(payload || "请求失败")}`.trim());
  }

  return payload as T;
}

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`);
  return parseJson<HealthResponse>(response);
}

export async function getRuntimeProfile(): Promise<RuntimeProfileResponse> {
  const response = await fetch(`${API_BASE}/system/runtime-profile`);
  return parseJson<RuntimeProfileResponse>(response);
}

export async function buildRealKnowledgeBase(params: {
  laws_path?: string;
  cases_path?: string;
  rebuild?: boolean;
}): Promise<IngestBuildResponse> {
  const response = await fetch(`${API_BASE}/system/build-real-kb`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return parseJson<IngestBuildResponse>(response);
}

export async function getMockCases(): Promise<CaseItem[]> {
  const response = await fetch(`${API_BASE}/cases`);
  const data = await parseJson<{ cases: CaseItem[] }>(response);
  return Array.isArray(data.cases) ? data.cases : [];
}


export async function getMockMediation(caseId: string): Promise<MediationResponse> {
  const response = await fetch(`${API_BASE}/mock/mediation/${caseId}`);
  return parseJson<MediationResponse>(response);
}

export async function createMediation(payload: { description: string; party_a?: string; party_b?: string }): Promise<MediationResponse> {
  const { description, ...rest } = payload;
  const requestBody = { case_description: description, ...rest };
  const response = await fetch(`${API_BASE}/mediation/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      case_description: payload.description,
      party_a: payload.party_a,
      party_b: payload.party_b
    }),
  });
  return parseJson<MediationResponse>(response);
}

export async function searchKnowledge(params: {
  q?: string;
  dispute_type?: string;
  region?: string;
  legal_limit?: number;
  case_limit?: number;
}): Promise<KnowledgeSearchResponse> {
  const searchParams = new URLSearchParams();
  if (params.q) searchParams.set("q", params.q);
  if (params.dispute_type) searchParams.set("dispute_type", params.dispute_type);
  if (params.region) searchParams.set("region", params.region);
  if (params.legal_limit) searchParams.set("legal_limit", String(params.legal_limit));
  if (params.case_limit) searchParams.set("case_limit", String(params.case_limit));

  const response = await fetch(`${API_BASE}/knowledge/search?${searchParams.toString()}`);
  return parseJson<KnowledgeSearchResponse>(response);
}
