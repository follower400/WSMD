import type { HistoryItem } from "@/types/mediation";

type Props = {
  history: HistoryItem[];
  onReuse: (item: HistoryItem) => void;
  onClear: () => void;
};

export default function HistoryPanel({ history, onReuse, onClear }: Props) {
  return (
    <section className="panel">
      <div className="panel-header panel-header-inline">
        <div>
          <h2>最近记录</h2>
          <p>本地保存最近 10 次调解请求，便于复用与演示。</p>
        </div>
        <button type="button" className="ghost-btn" onClick={onClear} disabled={history.length === 0}>
          清空记录
        </button>
      </div>

      {history.length === 0 ? (
        <div className="empty-box">暂无历史记录。先提交一次案件或查看 Mock 方案。</div>
      ) : (
        <div className="card-list">
          {history.map((item) => (
            <article key={`${item.created_at}-${item.response.case_id || "no-id"}`} className="case-card">
              <div className="case-card-top">
                <strong>{item.response.dispute_type || "未分类"}</strong>
                <span className="tag">{new Date(item.created_at).toLocaleString()}</span>
              </div>
              <p>{item.request.description}</p>
              <div className="meta-text">
                <span>{item.request.party_a || "未填写甲方"}</span>
                <span>{item.request.party_b || "未填写乙方"}</span>
                {item.request.preferred_region ? <span>{item.request.preferred_region}</span> : null}
              </div>
              <div className="action-row">
                <button type="button" onClick={() => onReuse(item)}>
                  重新载入
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
