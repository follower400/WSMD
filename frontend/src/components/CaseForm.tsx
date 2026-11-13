import { useEffect, useState } from "react";
import { createMediation } from "@/api/mediation";
import type { CaseItem, MediationRequest, MediationResponse } from "@/types/mediation";

type Props = {
  draftCase: CaseItem | null;
  onResult: (data: MediationResponse, request: MediationRequest) => void;
  onBusyChange: (busy: boolean) => void;
  onResetDraft: () => void;
};

const defaultForm: MediationRequest = {
  description: "邻居装修噪音太大，晚上十点后仍在施工，影响休息。",
  party_a: "张先生",
  party_b: "王女士",
  preferred_region: "北京",
};

export default function CaseForm({ draftCase, onResult, onBusyChange, onResetDraft }: Props) {
  const [form, setForm] = useState<MediationRequest>(defaultForm);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tip, setTip] = useState("");

  useEffect(() => {
    if (!draftCase) return;
    setForm((prev) => ({
      ...prev,
      description: draftCase.description || "",
      party_a: draftCase.party_a || "",
      party_b: draftCase.party_b || "",
    }));
    setTip(`已填入案例：${draftCase.id}`);
    setError("");
  }, [draftCase]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const request: MediationRequest = {
      ...form,
      description: (form.description || "").trim().replace(/\s+/g, " "),
      party_a: (form.party_a || "").trim() || undefined,
      party_b: (form.party_b || "").trim() || undefined,
      preferred_region: (form.preferred_region || "").trim() || undefined,
    };

    if ((request.description || "").length < 5) {
      setError("案件描述不能为空，且至少输入 5 个字符。");
      return;
    }

    setLoading(true);
    onBusyChange(true);
    setError("");
    setTip("");

    try {
      const data = await createMediation(request);
      onResult(data, request);
      setTip("调解建议已生成，可在右侧查看结果。已同步写入历史记录。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setLoading(false);
      onBusyChange(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>案件录入</h2>
          <p>输入案件描述并调用 /mediate 接口生成调解建议。</p>
        </div>
      </div>

      <form className="form-grid" onSubmit={handleSubmit}>
        <label>
          <span>案件描述</span>
          <textarea
            rows={7}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="请输入案件描述"
          />
        </label>

        <div className="two-col">
          <label>
            <span>当事人 A</span>
            <input
              value={form.party_a || ""}
              onChange={(e) => setForm({ ...form, party_a: e.target.value })}
              placeholder="例如：张先生"
            />
          </label>

          <label>
            <span>当事人 B</span>
            <input
              value={form.party_b || ""}
              onChange={(e) => setForm({ ...form, party_b: e.target.value })}
              placeholder="例如：王女士"
            />
          </label>
        </div>

        <label>
          <span>优先地区</span>
          <input
            value={form.preferred_region || ""}
            onChange={(e) => setForm({ ...form, preferred_region: e.target.value })}
            placeholder="例如：北京"
          />
        </label>

        <div className="action-row">
          <button type="submit" disabled={loading}>
            {loading ? "生成中..." : "生成调解建议"}
          </button>
          <button
            type="button"
            className="ghost-btn"
            onClick={() => {
              setForm(defaultForm);
              setTip("已恢复示例数据。\n");
              setError("");
              onResetDraft();
            }}
          >
            恢复示例数据
          </button>
        </div>

        {tip ? <div className="tip-box">{tip}</div> : null}
        {error ? <div className="error-box">{error}</div> : null}
      </form>
    </section>
  );
}
