import { useEffect, useState } from "react";
import { getMockCases, getMockMediation } from "@/api/mediation";
import type { CaseItem, MediationRequest, MediationResponse } from "@/types/mediation";

type Props = {
  selectedCaseId: string | null;
  onSelectCase: (item: CaseItem) => void;
  onResult: (result: MediationResponse, request: MediationRequest) => void;
  onBusyChange: (busy: boolean) => void;
};

export default function MockCaseList({ selectedCaseId, onSelectCase, onResult, onBusyChange }: Props) {
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewLoadingId, setPreviewLoadingId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function loadCases() {
    setLoading(true);
    setError("");

    try {
      const data = await getMockCases();
      setCases(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载案例失败");
    } finally {
      setLoading(false);
    }
  }

  async function previewMediation(item: CaseItem) {
    setError("");
    setPreviewLoadingId(item.id);
    onSelectCase(item);
    onBusyChange(true);
    try {
      const result = await getMockMediation(item.id);
      onResult(result, {
        description: item.description,
        party_a: item.party_a,
        party_b: item.party_b,
        preferred_region: "北京",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取调解方案失败");
    } finally {
      setPreviewLoadingId(null);
      onBusyChange(false);
    }
  }

  useEffect(() => {
    void loadCases();
  }, []);

  return (
    <section className="panel">
      <div className="panel-header panel-header-inline">
        <div>
          <h2>Mock 案例列表</h2>
          <p>调用 /mock/cases 获取演示数据，并支持一键填表或查看模拟方案。</p>
        </div>
        <button onClick={() => void loadCases()} disabled={loading}>
          {loading ? "刷新中..." : "刷新案例"}
        </button>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="card-list">
        {loading ? <div className="tip-box">正在加载案例列表...</div> : null}

        {cases.length === 0 && !loading ? <div className="empty-box">暂无案例，请检查后端 Mock 接口。</div> : null}

        {cases.map((item) => {
          const isSelected = selectedCaseId === item.id;
          const previewing = previewLoadingId === item.id;
          return (
            <article key={item.id} className={`case-card ${isSelected ? "case-card-active" : ""}`}>
              <div className="case-card-top">
                <strong>{item.dispute_type || "未分类案件"}</strong>
                {item.status ? <span className="tag">{item.status}</span> : null}
              </div>
              <p>{item.description}</p>
              <div className="meta-text">
                <span>{item.party_a || "未知甲方"}</span>
                <span>{item.party_b || "未知乙方"}</span>
                {item.date ? <span>{item.date}</span> : null}
              </div>
              <div className="action-row">
                <button type="button" onClick={() => onSelectCase(item)}>
                  填入表单
                </button>
                <button type="button" className="ghost-btn" onClick={() => void previewMediation(item)} disabled={previewing}>
                  {previewing ? "加载中..." : "查看模拟方案"}
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
