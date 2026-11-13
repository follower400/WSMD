import type { MediationResponse } from "@/types/mediation";

type Props = {
  result: MediationResponse | null;
  busy: boolean;
  selectedCaseId: string | null;
};

function getSourceLabel(source: MediationResponse["source"]): string {
  if (source === "mock") return "Mock 演示数据";
  if (source === "live") return "实时生成结果";
  return "系统结果";
}

function getRiskLabel(riskLevel: MediationResponse["risk_level"]): string {
  if (riskLevel === "high") return "高风险";
  if (riskLevel === "low") return "低风险";
  return "中风险";
}

function getEmotionLabel(level?: string) {
  if (level === "escalated") return "冲突升级";
  if (level === "tense") return "情绪紧张";
  return "相对平稳";
}

export default function ResultPanel({ result, busy, selectedCaseId }: Props) {
  return (
    <section className="panel result-panel">
      <div className="panel-header">
        <div>
          <h2>调解结果</h2>
          <p>展示后端返回的纠纷类型、法规依据、案例参考、情绪引导和人工复核提示。</p>
        </div>
      </div>

      {busy ? <div className="tip-box">正在请求后端，请稍候...</div> : null}

      {!result ? (
        <div className="empty-box">
          暂无调解结果。请先提交案件，或从左侧选择一个 Mock 案例查看方案。
          {selectedCaseId ? <div className="subtle-text">当前已选择案例：{selectedCaseId}</div> : null}
        </div>
      ) : (
        <div className="result-grid">
          <div className="info-box"><span className="info-label">案件 ID</span><strong>{result.case_id || "-"}</strong></div>
          <div className="info-box"><span className="info-label">纠纷类型</span><strong>{result.dispute_type || "-"}</strong></div>
          <div className="info-box"><span className="info-label">结果来源</span><strong>{getSourceLabel(result.source)}</strong></div>
          <div className="info-box"><span className="info-label">风险等级</span><strong>{getRiskLabel(result.risk_level)}</strong></div>
          <div className="info-box"><span className="info-label">识别置信度</span><strong>{result.confidence ? result.confidence.toFixed(2) : "-"}</strong></div>
          <div className="info-box"><span className="info-label">人工复核</span><strong>{result.needs_human_review ? "需要人工复核" : "未标记"}</strong></div>
          <div className="info-box detail-box-full"><span className="info-label">运行模式</span><strong>{result.runtime?.retrieval_mode || "未知"}</strong><div className="subtle-text">知识后端：{result.runtime?.knowledge_backend || "未知"} / 向量后端：{result.runtime?.vector_backend || "未知"} / 生成方式：{result.runtime?.generation_mode || "未知"}</div></div>

          <div className="detail-box detail-box-full">
            <h3>结果摘要</h3>
            <p>{result.summary || "暂无摘要。"}</p>
            {result.matched_keywords?.length ? <div className="keyword-row">{result.matched_keywords.map((item) => <span key={item} className="tag">{item}</span>)}</div> : null}
          </div>

          <div className="detail-box detail-box-full">
            <h3>情绪引导</h3>
            <div className="subtle-text">当前判断：{getEmotionLabel(result.emotion_guidance?.level)}</div>
            {result.emotion_guidance?.detected_signals?.length ? <div className="keyword-row">{result.emotion_guidance.detected_signals.map((item) => <span key={item} className="tag">{item}</span>)}</div> : null}
            {result.emotion_guidance?.mediator_tips?.length ? <ul>{result.emotion_guidance.mediator_tips.map((tip, index) => <li key={`tip-${index}`}>{tip}</li>)}</ul> : <p>暂无引导建议。</p>}
          </div>

          <div className="detail-box">
            <h3>法律依据</h3>
            {result.legal_basis?.length ? (
              <div className="reference-list">
                {result.legal_basis.map((item) => (
                  <article key={item.id} className="reference-card">
                    <div className="reference-top"><strong>{item.title}</strong><span className="tag">{item.source_level}</span></div>
                    <div className="subtle-text">{item.article}{item.region ? ` · ${item.region}` : ""}{item.score ? ` · 分数 ${item.score}` : ""}{item.effective_status ? ` · ${item.effective_status}` : ""}</div>
                    <p>{item.excerpt}</p>
                    {item.matched_tokens?.length ? <div className="keyword-row">{item.matched_tokens.map((token) => <span key={token} className="tag">{token}</span>)}</div> : null}{item.source_url ? <a className="subtle-link" href={item.source_url} target="_blank" rel="noreferrer">查看来源</a> : null}
                  </article>
                ))}
              </div>
            ) : <p>暂无返回内容。</p>}
          </div>

          <div className="detail-box">
            <h3>相似案例</h3>
            {result.case_references?.length ? (
              <div className="reference-list">
                {result.case_references.map((item) => (
                  <article key={item.id} className="reference-card">
                    <div className="reference-top"><strong>{item.title}</strong><span className="tag">案例</span></div>
                    <div className="subtle-text">{item.dispute_type}{item.region ? ` · ${item.region}` : ""}{item.score ? ` · 分数 ${item.score}` : ""}</div>
                    <p>{item.summary}</p>
                    {item.handling_points?.length ? <ul>{item.handling_points.map((point, index) => <li key={`${item.id}-${index}`}>{point}</li>)}</ul> : null}{item.source_url ? <a className="subtle-link" href={item.source_url} target="_blank" rel="noreferrer">查看案例来源</a> : null}
                  </article>
                ))}
              </div>
            ) : <p>暂无相似案例。</p>}
          </div>

          <div className="detail-box detail-box-full">
            <h3>调解步骤</h3>
            {result.steps?.length ? <ol>{result.steps.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ol> : <p>暂无返回内容。</p>}
          </div>
        </div>
      )}
    </section>
  );
}
