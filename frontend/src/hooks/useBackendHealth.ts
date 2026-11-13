import { useCallback, useEffect, useMemo, useState } from "react";
import { getHealth } from "@/api/mediation";
import type { HealthResponse } from "@/types/mediation";

export function useBackendHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthText, setHealthText] = useState("检查中...");

  const checkHealth = useCallback(async () => {
    setHealthText("检查中...");
    try {
      const data = await getHealth();
      setHealth(data);
      setHealthText(data.status === "ok" ? "后端已连接" : "后端状态异常");
    } catch {
      setHealth(null);
      setHealthText("后端未连接");
    }
  }, []);

  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);

  const statusClass = useMemo(() => {
    if (healthText === "后端已连接") return "status-ok";
    if (healthText === "检查中...") return "status-pending";
    return "status-error";
  }, [healthText]);

  return { health, healthText, statusClass, checkHealth };
}
