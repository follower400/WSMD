import { useState } from "react";
import { buildRealKnowledgeBase } from "@/api/mediation";
import { useRuntimeProfile } from "@/hooks/useRuntimeProfile";

export default function ArchitectureStatusPanel() {
  const { profile, loading, error, refresh } = useRuntimeProfile();
  const [building, setBuilding] = useState(false);
  const [buildMessage, setBuildMessage] = useState("");

  async function handleBuild() {
    setBuilding(true);
    setBuildMessage("");
    try {
      const data = await buildRealKnowledgeBase({ rebuild: true });
      setBuildMessage(`建库完成：法规 ${data.legal_chunks} 个 chunk，案例 ${data.case_chunks} 个 chunk。`);
      await refresh();
    } catch (err) {
      setBuildMessage(err instanceof Error ? err.message : "建库失败");
    } finally {
      setBuilding(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header panel-header-inline">
        <div>
          <h2>运行架构说明</h2>
          <p>这一页用于答辩演示：说明当前版本的知识库、检索链路、真实数据库接入方式和动态生成状态。</p>
        </div>
        <div className="action-row">
          <button type="button" onClick={() => void refresh()} disabled={loading}>{loading ? "刷新中..." : "刷新状态"}</button>
          <button type="button" className="ghost-btn" onClick={() => void handleBuild()} disabled={building}>{building ? "建库中..." : "重建真实检索库"}</button>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {buildMessage ? <div className="tip-box">{buildMessage}</div> : null}
      {!profile && !loading ? <div className="empty-box">暂无运行信息。</div> : null}

      {profile ? (
        <div className="result-grid">
          <div className="info-box"><span className="info-label">知识后端</span><strong>{profile.runtime.knowledge_backend}</strong></div>
          <div className="info-box"><span className="info-label">向量后端</span><strong>{profile.runtime.vector_backend}</strong></div>
          <div className="info-box"><span className="info-label">检索模式</span><strong>{profile.runtime.retrieval_mode}</strong></div>
          <div className="info-box"><span className="info-label">数据库连接</span><strong>{profile.runtime.database_connected ? "已连接" : "未连接"}</strong></div>
          <div className="info-box"><span className="info-label">生成方式</span><strong>{profile.runtime.generation_mode === "rag_llm" ? "RAG 动态生成" : "规则拼装"}</strong></div>
          <div className="info-box"><span className="info-label">Embedding 模型</span><strong>{profile.runtime.embedding_model || "未配置"}</strong></div>
          <div className="info-box"><span className="info-label">生成模型</span><strong>{profile.runtime.generation_model || "未配置"}</strong></div>
          <div className="info-box"><span className="info-label">法规条目数</span><strong>{profile.counts.legal_items}</strong></div>
          <div className="info-box"><span className="info-label">案例条目数</span><strong>{profile.counts.case_items}</strong></div>
          <div className="detail-box detail-box-full">
            <h3>当前运行逻辑</h3>
            <ol>
              <li>前端将案件描述发送给 /mediate。</li>
              <li>后端先做纠纷识别、风险判断和情绪引导。</li>
              <li>系统优先从 Chroma 双 collection 检索法规与案例；若不可用则回退到本地 JSON 双知识库。</li>
              <li>若已配置 Ollama 且检索可用，则基于检索证据调用本地大模型生成摘要和调解步骤。</li>
              <li>若大模型不可用，则自动回退到规则拼装结果，保证演示稳定。</li>
            </ol>
          </div>
          <div className="detail-box detail-box-full">
            <h3>如何接入真实法律数据库与大模型</h3>
            <ul>
              <li>把法规和案例导出为 JSON/JSONL 后，通过“重建真实检索库”写入 Chroma。</li>
              <li>在后端环境变量中配置 OLLAMA_BASE_URL 与 GENERATION_MODEL。</li>
              <li>运行模式会自动从 local_json 切到 chromadb，并在满足条件时切到 rag_llm。</li>
            </ul>
          </div>
          <div className="detail-box detail-box-full">
            <h3>当前版本的技术说明</h3>
            <ul>
              {profile.runtime.notes.map((note, index) => <li key={index}>{note}</li>)}
            </ul>
          </div>
        </div>
      ) : null}
    </section>
  );
}
