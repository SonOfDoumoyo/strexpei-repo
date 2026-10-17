import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Card, EmptyState, ErrorState, PageHeader, Pagination, Segmented, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { api } from "../../lib/api";
import { dateTime, naira } from "../../lib/format";
import type { Paged } from "../../lib/types";

type Run = { id: string; number: string; workgroup: string; status: string; trigger: string; staff_count: number; salaries_kobo: number; commission_kobo: number; total_kobo: number; paid_kobo: number; created_at: string; completed_at: string | null };

export default function AdminRuns() {
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({ queryKey: ["admin", "runs", status, page], queryFn: () => api.get<Paged<Run>>("/admin/payroll-runs", { status: status || undefined, page }), placeholderData: keepPreviousData, refetchInterval: 30_000 });
  return (
    <div>
      <PageHeader title="Payroll runs" description="Every payroll across the platform. Watch for runs stuck in processing or failing." />
      <div className="mb-4 overflow-x-auto">
        <Segmented value={status} onChange={(v) => { setStatus(v); setPage(1); }} options={[{ value: "", label: "All" }, { value: "processing", label: "Paying" }, { value: "awaiting_funding", label: "Awaiting funds" }, { value: "partially_failed", label: "Partly paid" }, { value: "failed", label: "Failed" }, { value: "completed", label: "Paid" }]} />
      </div>
      <Card className="overflow-hidden">
        {list.error ? <ErrorState error={list.error} /> : list.isLoading ? <div className="p-5"><Skeleton className="h-40" /></div> : !list.data?.items.length ? <EmptyState title="No payroll runs" /> : (
          <>
            <Table>
              <thead><tr><Th>Run</Th><Th>Status</Th><Th align="right">Staff</Th><Th align="right">Salaries</Th><Th align="right">Paid</Th><Th align="right">Fee earned</Th><Th>Created</Th></tr></thead>
              <tbody>
                {list.data.items.map((r) => (
                  <tr key={r.id}>
                    <Td><p className="font-medium">{r.workgroup}</p><p className="num text-[12px] text-ink-3">{r.number} · {r.trigger}</p></Td>
                    <Td><StatusPill status={r.status} /></Td>
                    <Td align="right">{r.staff_count}</Td>
                    <Td align="right">{naira(r.salaries_kobo)}</Td>
                    <Td align="right">{naira(r.paid_kobo)}</Td>
                    <Td align="right">{naira(r.commission_kobo)}</Td>
                    <Td className="text-ink-3">{dateTime(r.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={25} total={list.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
