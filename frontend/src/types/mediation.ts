export type HealthResponse = {
  status: string;
  service?: string;
  version?: string;
  knowledge_base_loaded?: boolean;
  retrieval_mode?: string;
  database_connected?: boolean;
};

export type ResultSource = "mock" | "live" | "system";
export type RiskLevel = "low" | "medium" | "high";
export type LegalSourceLevel = "national" | "local" | "case" | "community";
export type EmotionLevel = "stable" | "tense" | "escalated";
export type GenerationMode = "rule_based" | "rag_llm";

export type LegalReference = {
  id: string;
  title: string;
  article: string;
  excerpt: string;
  source_level: LegalSourceLevel;
  dispute_type?: string;
  region?: string;
  keywords?: string[];
  score?: number;
  matched_tokens?: string[];
  source_url?: string;
  effective_status?: string;
};

export type CaseReference = {
  id: string;
  title: string;
  summary: string;
  dispute_type: string;
  region?: string;
  keywords?: string[];
  handling_points?: string[];
  score?: number;
  matched_tokens?: string[];
  source_url?: string;
};

export type EmotionGuidance = {
  level: EmotionLevel;
  detected_signals: string[];
  mediator_tips: string[];
};

export type RuntimeProfile = {
  knowledge_backend: string;
  vector_backend: string;
  retrieval_mode: string;
  database_connected: boolean;
  supports_true_vector_search: boolean;
  supports_rag_generation: boolean;
  generation_model?: string | null;
  embedding_model?: string | null;
  generation_mode: GenerationMode;
  notes: string[];
};

export type RuntimeProfileResponse = {
  runtime: RuntimeProfile;
  counts: Record<string, number>;
};

export type IngestBuildResponse = {
  status: string;
  legal_chunks: number;
  case_chunks: number;
  law_collection: string;
  case_collection: string;
  runtime: RuntimeProfile;
};

export type CaseItem = {
  id: string;
  description: string;
  dispute_type?: string;
  party_a?: string;
  party_b?: string;
  date?: string;
  status?: string;
  resolution?: string | null;
  title?: string;
};

export type MediationRequest = {
  description: string;
  party_a?: string;
  party_b?: string;
  preferred_region?: string;
};

export type MediationResponse = {
  case_id?: string;
  dispute_type?: string;
  legal_basis?: LegalReference[];
  case_references?: CaseReference[];
  steps?: string[];
  needs_human_review?: boolean;
  source?: ResultSource;
  summary?: string;
  matched_keywords?: string[];
  risk_level?: RiskLevel;
  confidence?: number;
  emotion_guidance?: EmotionGuidance;
  runtime?: RuntimeProfile;
};

export type KnowledgeSearchResponse = {
  legal_items: LegalReference[];
  case_items: CaseReference[];
  total_legal: number;
  total_cases: number;
  runtime: RuntimeProfile;
};

export type HistoryItem = {
  created_at: string;
  request: MediationRequest;
  response: MediationResponse;
};
