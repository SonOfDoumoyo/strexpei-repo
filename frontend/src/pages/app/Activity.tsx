import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Card, EmptyState, ErrorState, PageHeader, Pagination, Segmented, Skeleton } from "../../components/ui";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { wgKey } from "../../lib/queries";
import type { AuditEntry, Paged } from "../../lib/types";

const FILTERS = [
  { value: "", label: "Everything" },
  { value: "payroll", label: "Payroll" },
  { value: "wallet", label: "Wallet" },
  { value: "staff", label: "Staff" },
  { value: "billing", label: "Billing" },
  { value: "assistant", label: "SPI" },
];

function dayKey(iso: string) {
  return new Date(iso).toLocaleDateString("en-NG", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

export default function Activity() {
  const workgroup = useWorkgroup();
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: wgKey(workgroup.id, "activity", filter, page),
    queryFn: () => api.get<Paged<AuditEntry>>(`/workgroups/${workgroup.id}/activity`, { action: filter || undefined, page, page_size: 40 }),
    placeholderData: keepPreviousData,
  });
  const groups: [string, AuditEntry[]][] = [];
  (q.data?.items ?? []).forEach((a) => {
    const key = dayKey(a.created_at);
    const last = groups[groups.length - 1];
    if (last && last[0] === key) last[1].push(a);
    else groups.push([key, [a]]);
  });

  return (
    <div>
      <PageHeader title="Activity" description="A permanent record of every change to this workgroup — who did it and when." />
      <div className="mb-4 overflow-x-auto">
        <Segmented value={filter} onChange={(v) => { setFilter(v); setPage(1); }} options={FILTERS} />
      </div>
      <Card className="overflow-hidden">
        {q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : q.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !groups.length ? (
          <EmptyState title="Nothing here yet">Actions on this workgroup are recorded here automatically.</EmptyState>
        ) : (
          <>
            {groups.map(([day, items]) => (
              <section key={day}>
                <h2 className="sticky top-[64px] z-10 border-b border-line bg-soft/80 px-5 py-2 text-[12.5px] font-semibold text-ink-2 backdrop-blur sm:px-6">{day}</h2>
                <ul className="divide-y divide-line">
                  {items.map((a) => (
                    <li key={a.id} className="flex items-start gap-4 px-5 py-3.5 sm:px-6">
                      <span className="num w-16 shrink-0 pt-0.5 text-[12px] text-ink-3">{new Date(a.created_at).toLocaleTimeString("en-NG", { hour: "numeric", minute: "2-digit" })}</span>
                      <div className="min-w-0">
                        <p className="text-[13.5px] leading-5">{a.summary}</p>
                        <p className="mt-0.5 text-[12px] text-ink-3">{a.actor}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            <Pagination page={page} pageSize={40} total={q.data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </Card>
      <p className="mt-3 text-[12px] text-ink-3">Times are shown in your device's time zone.</p>
    </div>
  );
}
