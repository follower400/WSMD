import { useEffect, useState } from "react";
import type { HistoryItem, MediationRequest, MediationResponse } from "@/types/mediation";

const STORAGE_KEY = "wisdom-mediator-history";
const MAX_ITEMS = 10;

export function useCaseHistory() {
  const [history, setHistory] = useState<HistoryItem[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as HistoryItem[];
        setHistory(Array.isArray(parsed) ? parsed : []);
      }
    } catch {
      setHistory([]);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  function pushHistory(request: MediationRequest, response: MediationResponse) {
    setHistory((prev) => [
      {
        created_at: new Date().toISOString(),
        request,
        response,
      },
      ...prev,
    ].slice(0, MAX_ITEMS));
  }

  function clearHistory() {
    setHistory([]);
  }

  return { history, pushHistory, clearHistory };
}
