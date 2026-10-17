import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Workgroup } from "../lib/types";
import { useAuth } from "./auth";

type Ctx = {
  workgroups: Workgroup[];
  workgroup: Workgroup | null;
  loading: boolean;
  select: (id: string) => void;
  refresh: () => Promise<unknown>;
};

const WorkgroupContext = createContext<Ctx | null>(null);
const KEY = "spx.workgroup";

export function WorkgroupProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const enabled = user?.role === "manager";
  const query = useQuery({ queryKey: ["workgroups"], queryFn: () => api.get<Workgroup[]>("/workgroups"), enabled, staleTime: 30_000 });
  const [selected, setSelected] = useState<string | null>(() => {
    try {
      return localStorage.getItem(KEY);
    } catch {
      return null;
    }
  });

  const workgroups = useMemo(() => query.data ?? [], [query.data]);
  const workgroup = workgroups.find((w) => w.id === selected) ?? workgroups[0] ?? null;

  useEffect(() => {
    if (workgroup && workgroup.id !== selected) setSelected(workgroup.id);
  }, [workgroup, selected]);

  const select = useCallback(
    (id: string) => {
      setSelected(id);
      try {
        localStorage.setItem(KEY, id);
      } catch {
        /* ignore */
      }
      queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] === "wg" });
    },
    [queryClient],
  );

  const value = useMemo<Ctx>(
    () => ({ workgroups, workgroup, loading: enabled ? query.isLoading : false, select, refresh: () => query.refetch() }),
    [workgroups, workgroup, enabled, query, select],
  );
  return <WorkgroupContext.Provider value={value}>{children}</WorkgroupContext.Provider>;
}

export function useWorkgroups() {
  const ctx = useContext(WorkgroupContext);
  if (!ctx) throw new Error("useWorkgroups must be used inside WorkgroupProvider");
  return ctx;
}

/** The active workgroup; only use under routes that guarantee one exists. */
export function useWorkgroup(): Workgroup {
  const { workgroup } = useWorkgroups();
  if (!workgroup) throw new Error("No active workgroup");
  return workgroup;
}
