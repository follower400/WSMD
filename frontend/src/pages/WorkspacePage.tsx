import { useState, useEffect } from 'react';
import { getPresetCases, createMediation } from '../api/mediation';
import type { CaseItem, MediationResponse } from '../types/mediation';
import ResultPanel from '../components/ResultPanel';

export default function WorkspacePage() {
  const [presetCases, setPresetCases] = useState<CaseItem[]>([]);
  const [description, setDescription] = useState('');
  const [partyA, setPartyA] = useState('');
  const [partyB, setPartyB] = useState('');
  const [result, setResult] = useState<MediationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPresetCases()
      .then(data => {
        const cases = data.cases || [];
        setPresetCases(cases);
      })
      .catch(err => setError(err instanceof Error ? err.message : '获取案例失败'));
  }, []);

  const handleSelectCase = (caseDesc: string) => {
    setDescription(caseDesc);
  };

  const handleSubmit = async () => {
    if (!description.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await createMediation({
        description,
        party_a: partyA,
        party_b: partyB
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : '调解生成失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="workspace" style={{ padding: '20px' }}>
      <section>
        <h3>预设案例</h3>
        <ul>
          {presetCases.map(c => (
            <li
              key={c.id}
              onClick={() => handleSelectCase(c.description)}
              style={{ cursor: 'pointer', marginBottom: '8px' }}
            >
              {/* 只使用 description，确保不依赖 title */}
              {c.description ? c.description.substring(0, 40) : c.id}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3>自由输入</h3>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          rows={4}
          style={{ width: '100%', marginBottom: '8px' }}
        />
        <input
          placeholder="甲方称呼"
          value={partyA}
          onChange={e => setPartyA(e.target.value)}
          style={{ marginRight: '8px' }}
        />
        <input
          placeholder="乙方称呼"
          value={partyB}
          onChange={e => setPartyB(e.target.value)}
        />
        <button onClick={handleSubmit} disabled={loading} style={{ marginTop: '8px', display: 'block' }}>
          {loading ? '生成中...' : '生成调解方案'}
        </button>
      </section>

      {error && (
        <section style={{ marginTop: '16px', padding: '12px', background: '#fdecea', color: '#b71c1c', borderRadius: '4px' }}>
          <strong>请求失败：</strong>{error}
        </section>
      )}

      <section style={{ marginTop: '16px' }}>
        <ResultPanel result={result} busy={loading} selectedCaseId={null} />
      </section>
    </div>
  );
}