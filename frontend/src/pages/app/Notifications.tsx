import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bell, CheckCircle2, Info, XCircle } from "lucide-react";
import { Button, Card, cx, EmptyState, ErrorState, PageHeader, Pagination, Segmented, Skeleton } from "../../components/ui";
import { useWorkgroups } from "../../context/workgroup";
import { api } from "../../lib/api";
import { relative } from "../../lib/format";
import type { Notification, Paged } from "../../lib/types";

export default function Notifications() {
  const [unread, setUnread] = useState<"all" | "unread">("all");
  const [page, setPage] = useState(1);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { workgroups, select } = useWorkgroups();
  const q = useQuery({
    queryKey: ["notifications", unread, page],
    queryFn: () => api.get<Paged<Notification> & { unread: number }>("/notifications", { unread: unread === "unread" || undefined, page, page_size: 30 }),
    placeholderData: keepPreviousData,
  });
  const markAll = useMutation({
    mutationFn: () => api.post("/notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
  const open = async (n: Notification) => {
    if (!n.read) {
      await api.post(`/notifications/${n.id}/read`).catch(() => undefined);
      qc.invalidateQueries({ queryKey: ["notifications"] });
    }
    if (n.workgroup_id && workgroups.some((w) => w.id === n.workgroup_id)) select(n.workgroup_id);
    if (n.link) navigate(n.link);
  };
  const icons = { info: Info, success: CheckCircle2, warning: AlertTriangle, danger: XCircle };
  const colors = { info: "text-brand-strong dark:text-brand", success: "text-good", warning: "text-warn", danger: "text-bad" };

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Notifications"
        description="Registrations, payments and anything that needs your attention."
        action={q.data?.unread ? <Button variant="secondary" loading={markAll.isPending} onClick={() => markAll.mutate()}>Mark all as read</Button> : undefined}
      />
      <div className="mb-4">
        <Segmented value={unread} onChange={(v) => { setUnread(v); setPage(1); }} options={[{ value: "all", label: "All" }, { value: "unread", label: "Unread", count: q.data?.unread }]} />
      </div>
      <Card className="overflow-hidden">
        {q.error ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : q.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
        ) : !q.data?.items.length ? (
          <EmptyState icon={<Bell size={20} />} title={unread === "unread" ? "You're all caught up" : "No notifications yet"}>
            We'll let you know when staff register, money arrives, or payroll finishes.
          </EmptyState>
        ) : (
          <>
            <ul className="divide-y divide-line">
              {q.data.items.map((n) => {
                const Icon = icons[n.kind] ?? Info;
                return (
                  <li key={n.id}>
                    <button type="button" onClick={() => open(n)} className={cx("flex w-full gap-4 px-5 py-4 text-left transition hover:bg-soft/40 sm:px-6", !n.read && "bg-brand-soft/30")}>
                      <Icon size={18} className={cx("mt-0.5 shrink-0", colors[n.kind])} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <p className={cx("text-[14px] leading-5", !n.read ? "font-semibold" : "font-medium")}>{n.title}</p>
                          <span className="shrink-0 text-[12px] text-ink-3">{relative(n.created_at)}</span>
                        </div>
                        <p className="mt-1 text-[13px] leading-5 text-ink-2">{n.body}</p>
                      </div>
                      {!n.read && <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
                    </button>
                  </li>
                );
              })}
            </ul>
            <Pagination page={page} pageSize={30} total={q.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
