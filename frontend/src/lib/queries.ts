import { useQuery } from "@tanstack/react-query";
import { api, publicApi } from "./api";
import type { Bank, Meta } from "./types";

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: () => publicApi.get<Meta>("/meta"), staleTime: 10 * 60_000 });
}

export function useBanks() {
  return useQuery({ queryKey: ["banks"], queryFn: () => publicApi.get<Bank[]>("/banks"), staleTime: 60 * 60_000 });
}

export function useUnreadCount(enabled: boolean) {
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => api.get<{ unread: number }>("/notifications/unread-count"),
    enabled,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

/** Query key namespace scoped to a workgroup so switching workgroups refetches. */
export const wgKey = (workgroupId: string, ...rest: unknown[]) => ["wg", workgroupId, ...rest];
