import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, FileSpreadsheet, Plus, Search, Trash2 } from "lucide-react";
import { GenerateIds, ImportIds } from "../../components/StaffIdTools";
import { Button, Card, EmptyState, ErrorState, IconButton, Input, Menu, MenuItem, Modal, PageHeader, Pagination, Progress, Segmented, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { date, plural } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { IdsSummary, Paged, Staff } from "../../lib/types";

type Filter = "all" | "pending" | "registered" | "inactive";

export default function StaffIds() {
  const workgroup = useWorkgroup();
  const [params, setParams] = useSearchParams();
  const filter = (params.get("status") as Filter) || "all";
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [adding, setAdding] = useState<null | "generate" | "import">(null);
  const [confirmPurge, setConfirmPurge] = useState(false);
  const toast = useToast();
  const qc = useQueryClient();

  const summary = useQuery({ queryKey: wgKey(workgroup.id, "ids-summary"), queryFn: () => api.get<IdsSummary>(`/workgroups/${workgroup.id}/staff-ids/summary`) });
  const list = useQuery({
    queryKey: wgKey(workgroup.id, "staff", filter, q, page),
    queryFn: () => api.get<Paged<Staff>>(`/workgroups/${workgroup.id}/staff`, { status: filter === "all" ? undefined : filter, q: q || undefined, page, page_size: 50 }),
    placeholderData: keepPreviousData,
  });
  const unclaimed = useQuery({
    queryKey: wgKey(workgroup.id, "staff", "pending-count"),
    queryFn: () => api.get<Paged<Staff>>(`/workgroups/${workgroup.id}/staff`, { status: "pending", page_size: 1 }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
  const remove = useMutation({
    mutationFn: (id: string) => api.delete<{ outcome: string }>(`/workgroups/${workgroup.id}/staff/${id}`),
    onSuccess: (r) => {
      toast.success(r.outcome === "deleted" ? "Staff ID deleted" : "Staff member deactivated");
      invalidate();
    },
    onError: (e) => toast.error(e),
  });
  const purge = useMutation({
    mutationFn: () => api.post<{ deleted: number }>(`/workgroups/${workgroup.id}/staff-ids/delete-unclaimed`, {}),
    onSuccess: (r) => {
      toast.success(`${plural(r.deleted, "unclaimed ID")} deleted`);
      setConfirmPurge(false);
      invalidate();
    },
    onError: (e) => toast.error(e),
  });

  const s = summary.data;
  const pendingCount = unclaimed.data?.total ?? 0;

  return (
    <div>
      <PageHeader
        title="Staff IDs"
        description="Staff register with one of these IDs. Only IDs on this list are accepted, and each one can be claimed once."
        action={
          <>
            <Menu
              trigger={({ toggle }) => (
                <Button variant="secondary" icon={<Download size={16} />} onClick={toggle}>
                  Export
                </Button>
              )}
            >
              {(close) => (
                <>
                  <MenuItem icon={<FileSpreadsheet size={16} />} onClick={() => { close(); void api.download(`/workgroups/${workgroup.id}/staff-ids/export`, "staff-ids.xlsx", { format: "xlsx" }).catch(toast.error); }}>
                    Excel (.xlsx)
                  </MenuItem>
                  <MenuItem icon={<Download size={16} />} onClick={() => { close(); void api.download(`/workgroups/${workgroup.id}/staff-ids/export`, "staff-ids.csv").catch(toast.error); }}>
                    CSV
                  </MenuItem>
                </>
              )}
            </Menu>
            <Menu
              trigger={({ toggle }) => (
                <Button icon={<Plus size={16} />} onClick={toggle}>
                  Add IDs
                </Button>
              )}
            >
              {(close) => (
                <>
                  <MenuItem onClick={() => { close(); setAdding("generate"); }}>Generate new IDs</MenuItem>
                  <MenuItem onClick={() => { close(); setAdding("import"); }}>Upload or paste our IDs</MenuItem>
                </>
              )}
            </Menu>
          </>
        }
      />

      <Card className="mb-6 p-5 sm:p-6">
        {s ? (
          <div className="grid gap-5 md:grid-cols-[1fr_auto] md:items-center">
            <div>
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="font-display text-[24px] font-semibold">
                  {s.in_use} <span className="text-[16px] font-medium text-ink-3">of {s.headcount} seats used</span>
                </p>
                <p className="text-[13px] text-ink-3">
                  {plural(pendingCount, "ID")} waiting to be claimed · {plural(s.remaining, "seat")} free
                </p>
              </div>
              <Progress value={s.in_use} max={s.headcount} className="mt-3 max-w-xl" label="Seats used" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to="/app/billing?seats=1" className="inline-flex h-9 items-center rounded-xl border border-line bg-raised px-3 text-[13px] font-semibold hover:border-line-strong">
                Change staff count
              </Link>
              {pendingCount > 0 && (
                <Button size="sm" variant="ghost" icon={<Trash2 size={14} />} onClick={() => setConfirmPurge(true)}>
                  Delete unclaimed
                </Button>
              )}
            </div>
          </div>
        ) : (
          <Skeleton className="h-14" />
        )}
      </Card>

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between">
          <Segmented<Filter>
            value={filter}
            onChange={(v) => {
              setPage(1);
              setParams(v === "all" ? {} : { status: v });
            }}
            options={[
              { value: "all", label: "All" },
              { value: "pending", label: "Unclaimed" },
              { value: "registered", label: "Registered" },
              { value: "inactive", label: "Inactive" },
            ]}
          />
          <div className="w-full sm:max-w-xs">
            <Input leading={<Search size={15} />} placeholder="Search ID or name" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search staff IDs" />
          </div>
        </div>
        {list.error ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : list.data && list.data.items.length === 0 ? (
          <EmptyState
            title={q || filter !== "all" ? "No matching staff IDs" : "No staff IDs yet"}
            action={!q && filter === "all" && (
              <>
                <Button onClick={() => setAdding("generate")}>Generate IDs</Button>
                <Button variant="secondary" onClick={() => setAdding("import")}>Upload our IDs</Button>
              </>
            )}
          >
            {!q && filter === "all" ? "Create an ID for each staff member, or upload the employee numbers you already use." : "Try a different filter or search."}
          </EmptyState>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Staff ID</Th>
                  <Th>Status</Th>
                  <Th>Name on your list</Th>
                  <Th>Registered as</Th>
                  <Th>Source</Th>
                  <Th>Added</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {list.data?.items.map((m) => (
                  <tr key={m.id} className="transition hover:bg-soft/40">
                    <Td className="num font-semibold tracking-wide">{m.staff_code}</Td>
                    <Td>
                      <StatusPill status={m.status} />
                    </Td>
                    <Td className="text-ink-2">{m.preset_name ?? "—"}</Td>
                    <Td>{m.registered_at ? <Link to={`/app/staff?focus=${m.id}`} className="font-medium hover:underline">{m.name}</Link> : <span className="text-ink-3">—</span>}</Td>
                    <Td className="capitalize text-ink-2">{m.source}</Td>
                    <Td className="text-ink-3">{date(m.created_at)}</Td>
                    <Td align="right">
                      {m.status === "pending" && (
                        <IconButton label={`Delete ${m.staff_code}`} onClick={() => remove.mutate(m.id)} disabled={remove.isPending}>
                          <Trash2 size={15} />
                        </IconButton>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={50} total={list.data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </Card>

      <Modal open={adding !== null} onClose={() => setAdding(null)} title={adding === "generate" ? "Generate staff IDs" : "Add your own staff IDs"} description={adding === "generate" ? "Create unique IDs and hand one to each staff member." : "Upload the employee numbers you already use."}>
        {adding === "generate" && s && <GenerateIds workgroup={workgroup} remaining={s.remaining} />}
        {adding === "import" && <ImportIds workgroup={workgroup} />}
      </Modal>

      <Modal
        open={confirmPurge}
        onClose={() => setConfirmPurge(false)}
        size="sm"
        title="Delete unclaimed IDs?"
        description={`${plural(pendingCount, "staff ID")} that nobody has registered with will be removed and their seats freed. Registered staff aren't affected.`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmPurge(false)}>Keep them</Button>
            <Button variant="danger" loading={purge.isPending} onClick={() => purge.mutate()}>Delete {plural(pendingCount, "ID")}</Button>
          </>
        }
      />
    </div>
  );
}
