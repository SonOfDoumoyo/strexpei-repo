import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Card, EmptyState, ErrorState, Input, PageHeader, Pagination, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { api } from "../../lib/api";
import { date, naira } from "../../lib/format";
import type { Paged } from "../../lib/types";

type Row = { id: string; name: string; owner: string | null; owner_email: string | null; status: string; headcount: number; registered_staff: number; wallet_balance_kobo: number; payment_mode: string; plan: string | null; subscription_status: string | null; disbursed_kobo: number; commission_kobo: number; created_at: string };

export default function AdminWorkgroups() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({ queryKey: ["admin", "workgroups", q, page], queryFn: () => api.get<Paged<Row>>("/admin/workgroups", { q: q || undefined, page }), placeholderData: keepPreviousData });
  return (
    <div>
      <PageHeader title="Workgroups" description="Every business paying staff through Streixpei, and what each earns you." />
      <Card className="overflow-hidden">
        <div className="border-b border-line p-4"><div className="max-w-sm"><Input leading={<Search size={15} />} placeholder="Search workgroups" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div></div>
        {list.error ? <ErrorState error={list.error} /> : list.isLoading ? <div className="p-5"><Skeleton className="h-40" /></div> : !list.data?.items.length ? <EmptyState title="No workgroups yet" /> : (
          <>
            <Table>
              <thead><tr><Th>Workgroup</Th><Th>Plan</Th><Th align="right">Staff</Th><Th align="right">Wallet</Th><Th align="right">Disbursed</Th><Th align="right">Fees earned</Th><Th>Created</Th></tr></thead>
              <tbody>
                {list.data.items.map((w) => (
                  <tr key={w.id}>
                    <Td><p className="font-medium">{w.name}{w.status !== "active" && <span className="ml-1.5 text-[12px] text-ink-3">(deleted)</span>}</p><p className="text-[12px] text-ink-3">{w.owner} · {w.owner_email}</p></Td>
                    <Td>{w.subscription_status ? <><StatusPill status={w.subscription_status} /><p className="mt-0.5 text-[12px] text-ink-3">{w.plan} · {w.payment_mode}</p></> : "—"}</Td>
                    <Td align="right">{w.registered_staff} / {w.headcount}</Td>
                    <Td align="right">{naira(w.wallet_balance_kobo)}</Td>
                    <Td align="right">{naira(w.disbursed_kobo)}</Td>
                    <Td align="right" className="font-medium">{naira(w.commission_kobo)}</Td>
                    <Td className="text-ink-3">{date(w.created_at)}</Td>
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
