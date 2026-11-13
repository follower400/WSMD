import { useCallback, useEffect, useState } from "react";
import { getRuntimeProfile } from "@/api/mediation";
import type { RuntimeProfileResponse } from "@/types/mediation";

export function useRuntimeProfile() {
  const [profile, setProfile] = useState<RuntimeProfileResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getRuntimeProfile();
      setProfile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取运行信息失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { profile, loading, error, refresh };
}
