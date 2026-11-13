import { useState } from "react";
import { searchKnowledge } from "@/api/mediation";
import type { CaseReference, LegalReference, RuntimeProfile } from "@/types/mediation";

export default function KnowledgeSearchPanel() {
  const [query, setQuery] = useState("噪音");
  const [disputeType, setDisputeType] = useState("邻里纠纷");
  const [region, setRegion] = useState("北京");
  const [legalItems, setLegalItems] = useState<LegalReference[]>([]);
  const [caseItems, setCaseItems] = useState<CaseReference[]>([]);
  const [runtime, setRuntime] = useState<RuntimeProfile | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSearch() {
    setLoading(true);
    setError("");
    try {
      const data = await searchKnowledge({ q: query, dispute_type: disputeType || undefined, region: region || undefined, legal_limit: 8, case_limit: 5 });
      setLegalItems(data.legal_items);
      setCaseItems(data.case_items);
      setRuntime(data.runtime);
    } catch (err) {
      setError(err instanceof Error ? err.message : "搜索失败");
      setLegalItems([]);
      setCaseItems([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>法律知识检索</h2>
          <p>同时检索法规库与案例库。若已完成 Chroma 建库，则优先走真实向量检索；否则自动回退到本地知识库。</p>
        </div>
      </div>

      <div className="form-grid">
        <div className="three-col">
          <label>
            <span>关键词</span>
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="例如：噪音、物业费" />
          </label>
          <label>
            <span>纠纷类型</span>
            <input value={disputeType} onChange={(e) => setDisputeType(e.target.value)} placeholder="例如：邻里纠纷" />
          </label>
          <label>
            <span>地区</span>
            <input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="例如：北京" />
          </label>
        </div>

        <div className="action-row">
          <button type="button" onClick={() => void handleSearch()} disabled={loading}>
            {loading ? "检索中..." : "开始检索"}
          </button>
        </div>

        {runtime ? <div className="tip-box">当前检索模式：{runtime.retrieval_mode} / {runtime.vector_backend} / 生成方式：{runtime.generation_mode}</div> : null}
        {error ? <div className="error-box">{error}</div> : null}

        {!loading && legalItems.length === 0 && caseItems.length === 0 ? <div className="empty-box">暂无检索结果。输入关键词后点击开始检索。</div> : null}

        {legalItems.length > 0 ? (
          <div className="detail-box">
            <h3>法规命中结果</h3>
            <div className="reference-list">
              {legalItems.map((item) => (
                <article key={item.id} className="reference-card">
                  <div className="reference-top">
                    <strong>{item.title}</strong>
                    <span className="tag">{item.source_level}</span>
                  </div>
                  <div className="subtle-text">{item.article}{item.region ? ` · ${item.region}` : ""}{item.score ? ` · 分数 ${item.score}` : ""}</div>
                  <p>{item.excerpt}</p>
                  {item.matched_tokens?.length ? <div className="keyword-row">{item.matched_tokens.map((keyword) => <span key={keyword} className="tag">{keyword}</span>)}</div> : null}
                </article>
              ))}
            </div>
          </div>
        ) : null}

        {caseItems.length > 0 ? (
          <div className="detail-box">
            <h3>相似案例结果</h3>
            <div className="reference-list">
              {caseItems.map((item) => (
                <article key={item.id} className="reference-card">
                  <div className="reference-top">
                    <strong>{item.title}</strong>
                    <span className="tag">案例</span>
                  </div>
                  <div className="subtle-text">{item.dispute_type}{item.region ? ` · ${item.region}` : ""}{item.score ? ` · 分数 ${item.score}` : ""}</div>
                  <p>{item.summary}</p>
                  {item.handling_points?.length ? <ul>{item.handling_points.map((point, index) => <li key={`${item.id}-${index}`}>{point}</li>)}</ul> : null}
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
