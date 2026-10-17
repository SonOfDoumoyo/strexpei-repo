import { useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { Button, Card, EmptyState, ErrorState, Input, PageHeader, Pagination, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { api } from "../../lib/api";
import { date, relative } from "../../lib/format";
import type { Paged } from "../../lib/types";

type AdminUser = { id: string; email: string; name: string; phone: string | null; role: string; status: string; verified: boolean; workgroups: number; created_at: string; last_login_at: string | null };

export default function AdminUsers() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const toast = useToast();
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["admin", "users", q, page], queryFn: () => api.get<Paged<AdminUser>>("/admin/users", { q: q || undefined, page }), placeholderData: keepPreviousData });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: "active" | "suspended" }) => api.patch(`/admin/users/${id}`, { status }),
    onSuccess: (_, v) => {
      toast.success(v.status === "suspended" ? "Account suspended" : "Account reactivated");
      qc.invalidateQueries({ queryKey: ["admin", "users"] });
    },
    onError: (e) => toast.error(e),
  });
  return (
    <div>
      <PageHeader title="Managers" description="Everyone who has signed up to run payroll." />
      <Card className="overflow-hidden">
        <div className="border-b border-line p-4">
          <div className="max-w-sm"><Input leading={<Search size={15} />} placeholder="Search name or email" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
        </div>
        {list.error ? <ErrorState error={list.error} /> : list.isLoading ? <div className="p-5"><Skeleton className="h-40" /></div> : !list.data?.items.length ? <EmptyState title="No managers found" /> : (
          <>
            <Table>
              <thead><tr><Th>Manager</Th><Th>Status</Th><Th align="right">Workgroups</Th><Th>Joined</Th><Th>Last sign-in</Th><Th /></tr></thead>
              <tbody>
                {list.data.items.map((u) => (
                  <tr key={u.id}>
                    <Td><p className="font-medium">{u.name} {u.role === "admin" && <span className="text-[12px] text-ink-3">(admin)</span>}</p><p className="text-[12px] text-ink-3">{u.email}{!u.verified && " · unverified"}</p></Td>
                    <Td><StatusPill status={u.status} /></Td>
                    <Td align="right">{u.workgroups}</Td>
                    <Td className="text-ink-3">{date(u.created_at)}</Td>
                    <Td className="text-ink-3">{u.last_login_at ? relative(u.last_login_at) : "Never"}</Td>
                    <Td align="right">
                      {u.role !== "admin" && (u.status === "suspended" ? (
                        <Button size="sm" variant="secondary" onClick={() => setStatus.mutate({ id: u.id, status: "active" })}>Reactivate</Button>
                      ) : u.status === "active" ? (
                        <Button size="sm" variant="ghost" className="text-bad" onClick={() => window.confirm(`Suspend ${u.email}? They'll be signed out immediately.`) && setStatus.mutate({ id: u.id, status: "suspended" })}>Suspend</Button>
                      ) : null)}
                    </Td>
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
