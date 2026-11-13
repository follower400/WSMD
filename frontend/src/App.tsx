import { NavLink, Route, Routes } from "react-router-dom";
import { API_BASE } from "@/lib/config";
import { useBackendHealth } from "@/hooks/useBackendHealth";
import WorkspacePage from "@/pages/WorkspacePage";
import KnowledgePage from "@/pages/KnowledgePage";
import RuntimePage from "@/pages/RuntimePage";

export default function App() {
  const { health, healthText, statusClass, checkHealth } = useBackendHealth();

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <span className="badge">V6</span>
          <h1>智慧调解助手前端工作台</h1>
          <p></p>
        </div>
        <div className="status-card">
          <div>
            <span className="info-label">API 地址</span>
            <strong>{API_BASE}</strong>
          </div>
          <div>
            <span className="info-label">连接状态</span>
            <strong className={statusClass}>{healthText}</strong>
            {health?.version ? <div className="subtle-text">版本：{health.version}</div> : null}
            <div className="subtle-text">知识库状态：{health?.knowledge_base_loaded ? "双知识库已加载" : "未完成加载"}</div>
            <div className="subtle-text">
              向量数据库：
              {health?.database_connected === undefined
                ? "状态未知"
                : health.database_connected
                  ? "Chroma 已连接"
                  : "使用本地知识库（Chroma 未连接）"}
            </div>
            <div className="subtle-text">检索模式：{health?.retrieval_mode || "未知"}</div>
          </div>
          <div className="action-row">
            <button type="button" className="ghost-btn" onClick={() => void checkHealth()}>
              重新检测连接
            </button>
          </div>
        </div>
      </header>

      <section className="notice-bar">
        <div>系统输出仅作辅助参考，不构成正式法律意见。</div>
        <div>建议调解员或相关专业人员人工复核后使用。</div>
      </section>

      <nav className="tab-bar">
        <NavLink to="/" end className={({ isActive }) => isActive ? "tab-btn active-tab" : "tab-btn"}>调解工作台</NavLink>
        <NavLink to="/knowledge" className={({ isActive }) => isActive ? "tab-btn active-tab" : "tab-btn"}>法律知识检索</NavLink>
        <NavLink to="/runtime" className={({ isActive }) => isActive ? "tab-btn active-tab" : "tab-btn"}>运行架构说明</NavLink>
      </nav>

      <Routes>
        <Route path="/" element={<WorkspacePage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/runtime" element={<RuntimePage />} />
      </Routes>
    </div>
  );
}
