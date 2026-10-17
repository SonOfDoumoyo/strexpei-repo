import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Receipt as ReceiptIcon } from "lucide-react";
import { Receipt } from "../../components/Receipt";
import { Button, ButtonLink, Card, CardHeader, cx, EmptyState, ErrorState, Notice, PageHeader, Pagination, Select, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup, useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { date, dayLong, naira, ordinal, plural } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Paged, PayrollRun, Preview, Workgroup } from "../../lib/types";

function ScheduleCard({ workgroup }: { workgroup: Workgroup }) {
  const toast = useToast();
  const { refresh } = useWorkgroups();
  const qc = useQueryClient();
  const [mode, setMode] = useState(workgroup.payment_mode);
  const [day, setDay] = useState(workgroup.payday_day);
  const [time, setTime] = useState(workgroup.payday_time);
  useEffect(() => {
    setMode(workgroup.payment_mode);
    setDay(workgroup.payday_day);
    setTime(workgroup.payday_time);
  }, [workgroup.payment_mode, workgroup.payday_day, workgroup.payday_time]);
  const dirty = mode !== workgroup.payment_mode || day !== workgroup.payday_day || time !== workgroup.payday_time;
  const save = useMutation({
    mutationFn: () => api.patch<Workgroup>(`/workgroups/${workgroup.id}`, { payment_mode: mode, payday_day: day, payday_time: time }),
    onSuccess: async (wg) => {
      await refresh();
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      toast.success("Payday saved", `Next payday: ${dayLong(wg.next_payday_at)}`);
    },
    onError: (e) => toast.error(e),
  });
  return (
    <Card>
      <CardHeader title="Payday" description={`Next: ${dayLong(workgroup.next_payday_at)} at ${workgroup.payday_time}`} />
      <div className="grid gap-5 p-5 sm:p-6">
        <div className="grid grid-cols-2 gap-2">
          {(["manual", "automatic"] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              onClick={() => setMode(m)}
              className={cx("rounded-xl border px-3 py-2.5 text-left transition", mode === m ? "border-brand bg-brand-soft/60" : "border-line hover:border-line-strong")}
            >
              <span className="block text-[13.5px] font-semibold capitalize">{m}</span>
              <span className="mt-0.5 block text-[12px] leading-5 text-ink-3">{m === "manual" ? "You fund and disburse" : "Paid from the wallet on payday"}</span>
            </button>
          ))}
        </div>
        {mode === "automatic" && (
          <p className="text-[12.5px] leading-5 text-ink-3">
            On payday we prepare payroll and pay everyone if the wallet covers it. If not, we email you the exact shortfall and pay as soon as it arrives.
          </p>
        )}
        <div className="grid grid-cols-[1fr_auto] gap-3">
          <Select label="Day" value={day} onChange={(e) => setDay(Number(e.target.value))}>
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>
                {d === 31 ? "Last day" : `${ordinal(d)} of the month`}
              </option>
            ))}
          </Select>
          <Select label="Time" value={time} onChange={(e) => setTime(e.target.value)}>
            {["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "15:00", "18:00"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </Select>
        </div>
        <div>
          <Button variant="dark" disabled={!dirty} loading={save.isPending} onClick={() => save.mutate()}>
            Save payday
          </Button>
        </div>
      </div>
    </Card>
  );
}

export default function Payroll() {
  const workgroup = useWorkgroup();
  const navigate = useNavigate();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [showNotReady, setShowNotReady] = useState(false);
  const preview = useQuery({ queryKey: wgKey(workgroup.id, "preview"), queryFn: () => api.get<Preview>(`/workgroups/${workgroup.id}/payroll/preview`) });
  const runs = useQuery({ queryKey: wgKey(workgroup.id, "runs", page), queryFn: () => api.get<Paged<PayrollRun>>(`/workgroups/${workgroup.id}/payroll/runs`, { page, page_size: 15 }) });
  const open = useQuery({
    queryKey: wgKey(workgroup.id, "runs", "open"),
    queryFn: () => api.get<Paged<PayrollRun>>(`/workgroups/${workgroup.id}/payroll/runs`, { status: "draft,awaiting_funding,ready,processing", page_size: 5 }),
  });
  const create = useMutation({
    mutationFn: () => api.post<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs`, {}),
    onSuccess: (run) => navigate(`/app/payroll/runs/${run.id}`),
    onError: (e) => toast.error(e),
  });

  const p = preview.data;
  const canPrepare = Boolean(p && p.items.length);
  const openRun = open.data?.items[0];

  return (
    <div>
      <PageHeader
        title="Payroll"
        description="Review what everyone gets, fund it, then pay all staff at once. Each staff member gets an email receipt."
        action={
          <Button size="lg" icon={<ReceiptIcon size={17} />} disabled={!canPrepare} loading={create.isPending} onClick={() => create.mutate()}>
            Prepare payroll
          </Button>
        }
      />

      {openRun && (
        <Notice
          tone="info"
          className="mb-6"
          title={`${openRun.period_label} payroll is ${openRun.status === "processing" ? "being paid" : openRun.status === "ready" ? "funded and ready to disburse" : openRun.status === "awaiting_funding" ? "waiting for funds" : "a draft"}`}
          action={<ButtonLink to={`/app/payroll/runs/${openRun.id}`} size="sm" variant="dark">Open {openRun.number}</ButtonLink>}
        >
          {plural(openRun.staff_count, "staff member")} · {naira(openRun.total_kobo)} total.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="grid content-start gap-6">
          {preview.error ? (
            <Card><ErrorState error={preview.error} onRetry={() => preview.refetch()} /></Card>
          ) : !p ? (
            <Skeleton className="h-72 rounded-[22px]" />
          ) : (
            <Receipt
              title={`If you paid everyone now · ${plural(p.items.length, "staff member")}`}
              lines={[
                { label: "Salaries", value: p.salaries_kobo },
                { label: "Paystack transfer fees", value: p.transfer_fees_kobo, muted: true },
                { label: `Streixpei service fee (${p.commission_label})`, value: p.commission_kobo, muted: true },
              ]}
              total={{ label: "Total from wallet", value: p.total_kobo }}
              footer={
                <div className="grid gap-3">
                  <div className="flex items-center justify-between text-[13.5px]">
                    <span className="text-ink-2">Wallet balance</span>
                    <span className="num font-semibold">{naira(p.wallet_balance_kobo)}</span>
                  </div>
                  {p.shortfall_kobo > 0 ? (
                    <div className="flex items-center justify-between text-[13.5px]">
                      <span className="text-warn">Still needed</span>
                      <span className="num font-semibold text-warn">{naira(p.shortfall_kobo)}</span>
                    </div>
                  ) : (
                    p.items.length > 0 && <p className="text-[13px] font-medium text-good">Your wallet covers this payroll.</p>
                  )}
                  {(p.not_ready.length > 0 || p.unregistered_count > 0) && (
                    <div className="border-t border-line pt-3">
                      <button type="button" onClick={() => setShowNotReady((v) => !v)} className="flex w-full items-center justify-between text-left text-[13px] font-medium text-ink-2">
                        <span>
                          {p.not_ready.length > 0 && `${plural(p.not_ready.length, "registered staff member")} can't be paid yet`}
                          {p.not_ready.length > 0 && p.unregistered_count > 0 && " · "}
                          {p.unregistered_count > 0 && `${plural(p.unregistered_count, "ID")} not registered`}
                        </span>
                        <ChevronDown size={15} className={cx("transition", showNotReady && "rotate-180")} />
                      </button>
                      {showNotReady && (
                        <ul className="mt-3 grid gap-1.5 text-[13px]">
                          {p.not_ready.map((n) => (
                            <li key={n.staff_id} className="flex justify-between gap-3">
                              <Link to={`/app/staff?focus=${n.staff_id}`} className="font-medium hover:underline">{n.staff_name || n.staff_code}</Link>
                              <span className="text-warn">{n.reasons.join(", ")}</span>
                            </li>
                          ))}
                          {p.unregistered_count > 0 && (
                            <li><Link to="/app/onboarding" className="font-medium text-brand-strong hover:underline dark:text-brand">Remind unregistered staff →</Link></li>
                          )}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              }
            />
          )}
          {p && p.items.length === 0 && (
            <Notice tone="warn" title="Nobody can be paid yet">
              Staff need to register their bank details with their staff ID, and have a salary set. <Link to="/app/onboarding" className="font-semibold underline">Share the onboarding link</Link> or <Link to="/app/staff" className="font-semibold underline">set salaries</Link>.
            </Notice>
          )}
        </div>
        <ScheduleCard workgroup={workgroup} />
      </div>

      <Card className="mt-6 overflow-hidden">
        <CardHeader title="Payroll history" />
        {runs.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11" />)}</div>
        ) : !runs.data?.items.length ? (
          <EmptyState title="No payroll runs yet">Prepared and paid payrolls are listed here with their receipts.</EmptyState>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Payroll</Th>
                  <Th>Status</Th>
                  <Th align="right">Staff</Th>
                  <Th align="right">Paid to staff</Th>
                  <Th align="right">Total</Th>
                  <Th>Created</Th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((r) => (
                  <tr key={r.id} className="cursor-pointer hover:bg-soft/40" onClick={() => navigate(`/app/payroll/runs/${r.id}`)}>
                    <Td>
                      <Link to={`/app/payroll/runs/${r.id}`} className="font-medium hover:underline" onClick={(e) => e.stopPropagation()}>
                        {r.period_label}
                      </Link>
                      <p className="num text-[12px] text-ink-3">
                        {r.number}
                        {r.trigger === "automatic" ? " · automatic" : r.trigger === "retry" ? " · retry" : ""}
                      </p>
                    </Td>
                    <Td><StatusPill status={r.status} /></Td>
                    <Td align="right">{r.staff_count}</Td>
                    <Td align="right">{naira(r.paid_kobo)}</Td>
                    <Td align="right" className="font-medium">{naira(r.total_kobo)}</Td>
                    <Td className="text-ink-3">{date(r.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={15} total={runs.data.total} onPage={setPage} />
          </>
        )}
      </Card>
      {create.error && (create.error as ApiError).code === "subscription_required" && <Notice tone="bad" className="mt-4">{(create.error as ApiError).message}</Notice>}
    </div>
  );
}
