import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck, ShieldAlert } from "lucide-react";
import { BarChart, DataTableToggle, Legend } from "../../components/charts";
import { Button, Card, CardHeader, ErrorState, Notice, PageHeader, PageLoader, Stat, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { api } from "../../lib/api";
import { monthLabel, naira, nairaCompact } from "../../lib/format";

type Overview = {
  revenue: { total_kobo: number; commission_kobo: number; subscriptions_kobo: number; this_month_kobo: number; commission_month_kobo: number; subscriptions_month_kobo: number; mrr_kobo: number };
  volume: { disbursed_kobo: number; wallets_held_kobo: number; paystack_balance_kobo: number | null };
  counts: { managers: number; workgroups: number; staff: number; payroll_runs_this_month: number };
  subscriptions: { by_status: Record<string, number>; by_plan: Record<string, number> };
  series: { month: string; commission_kobo: number; subscriptions_kobo: number; disbursed_kobo: number }[];
};

export default function AdminOverview() {
  const toast = useToast();
  const q = useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<Overview>("/admin/overview"), refetchInterval: 60_000 });
  const integrity = useQuery({ queryKey: ["admin", "integrity"], queryFn: () => api.get<{ ok: boolean; mismatches: { name: string; balance_kobo: number; ledger_kobo: number }[] }>("/admin/integrity") });
  if (q.isLoading) return <PageLoader />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const balanceShort = d.volume.paystack_balance_kobo !== null && d.volume.paystack_balance_kobo < d.volume.wallets_held_kobo;

  return (
    <div>
      <PageHeader
        title="Revenue"
        description="What Streixpei earns: subscriptions by staff count plus the service fee on every salary disbursed."
        action={<Button variant="secondary" icon={<Download size={15} />} onClick={() => api.download("/admin/revenue/export", "revenue.csv", { days: 365 }).catch(toast.error)}>Export 12 months</Button>}
      />
      {balanceShort && (
        <Notice tone="bad" className="mb-6" title="Paystack balance is below what managers hold">
          Wallets hold {naira(d.volume.wallets_held_kobo)} but the Paystack balance is {naira(d.volume.paystack_balance_kobo)}. Check that collections settle to the Paystack balance, or payroll transfers will fail.
        </Notice>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Revenue this month" value={naira(d.revenue.this_month_kobo)} sub={`${naira(d.revenue.commission_month_kobo)} fees · ${naira(d.revenue.subscriptions_month_kobo)} plans`} />
        <Stat label="Monthly recurring (plans)" value={naira(d.revenue.mrr_kobo)} sub={`${Object.values(d.subscriptions.by_plan).reduce((a, b) => a + b, 0)} paying workgroups`} />
        <Stat label="Revenue, all time" value={nairaCompact(d.revenue.total_kobo)} sub={`${nairaCompact(d.revenue.commission_kobo)} fees · ${nairaCompact(d.revenue.subscriptions_kobo)} plans`} />
        <Stat label="Salaries disbursed" value={nairaCompact(d.volume.disbursed_kobo)} sub={`${d.counts.payroll_runs_this_month} payroll runs this month`} />
      </div>

      <Card className="mt-6">
        <CardHeader title="Revenue by month" description="Service fees on disbursed salaries and subscription payments" action={<Legend items={[{ label: "Service fees", color: "var(--c-series-1)" }, { label: "Subscriptions", color: "var(--c-series-2)" }]} />} />
        <div className="p-5 sm:p-6">
          <DataTableToggle
            table={
              <Table>
                <thead><tr><Th>Month</Th><Th align="right">Service fees</Th><Th align="right">Subscriptions</Th><Th align="right">Disbursed</Th></tr></thead>
                <tbody>{d.series.map((s) => <tr key={s.month}><Td>{s.month}</Td><Td align="right">{naira(s.commission_kobo)}</Td><Td align="right">{naira(s.subscriptions_kobo)}</Td><Td align="right">{naira(s.disbursed_kobo)}</Td></tr>)}</tbody>
              </Table>
            }
          >
            <BarChart
              label="Revenue by month"
              series={2}
              format={nairaCompact}
              data={d.series.map((s) => ({
                key: s.month,
                label: monthLabel(s.month),
                values: [s.commission_kobo, s.subscriptions_kobo],
                detail: (
                  <div className="grid gap-0.5">
                    <p className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-series-1" /> Fees <span className="num ml-auto pl-3">{naira(s.commission_kobo)}</span></p>
                    <p className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm bg-series-2" /> Plans <span className="num ml-auto pl-3">{naira(s.subscriptions_kobo)}</span></p>
                    <p className="text-ink-3">Disbursed {nairaCompact(s.disbursed_kobo)}</p>
                  </div>
                ),
              }))}
            />
          </DataTableToggle>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="p-6">
          <p className="text-[13px] font-medium text-ink-2">Platform</p>
          <dl className="mt-4 grid gap-2.5 text-[13.5px]">
            {[["Managers", d.counts.managers], ["Active workgroups", d.counts.workgroups], ["Registered staff", d.counts.staff.toLocaleString()]].map(([k, v]) => (
              <div key={k as string} className="flex justify-between"><dt className="text-ink-2">{k}</dt><dd className="num font-semibold">{v}</dd></div>
            ))}
          </dl>
        </Card>
        <Card className="p-6">
          <p className="text-[13px] font-medium text-ink-2">Subscriptions</p>
          <dl className="mt-4 grid gap-2.5 text-[13.5px]">
            {Object.entries(d.subscriptions.by_status).map(([k, v]) => (
              <div key={k} className="flex justify-between"><dt className="capitalize text-ink-2">{k.replace("_", " ")}</dt><dd className="num font-semibold">{v}</dd></div>
            ))}
            {!Object.keys(d.subscriptions.by_status).length && <p className="text-ink-3">None yet</p>}
          </dl>
        </Card>
        <Card className="p-6">
          <p className="text-[13px] font-medium text-ink-2">Money held</p>
          <dl className="mt-4 grid gap-2.5 text-[13.5px]">
            <div className="flex justify-between"><dt className="text-ink-2">In manager wallets</dt><dd className="num font-semibold">{naira(d.volume.wallets_held_kobo)}</dd></div>
            <div className="flex justify-between"><dt className="text-ink-2">Paystack balance</dt><dd className="num font-semibold">{d.volume.paystack_balance_kobo === null ? "Unavailable" : naira(d.volume.paystack_balance_kobo)}</dd></div>
          </dl>
          <div className="mt-4 flex items-center gap-2 border-t border-line pt-4 text-[13px]">
            {integrity.data?.ok ? <ShieldCheck size={16} className="text-good" /> : <ShieldAlert size={16} className="text-bad" />}
            {integrity.isLoading ? "Checking ledger…" : integrity.data?.ok ? "Every wallet matches its ledger" : `${integrity.data?.mismatches.length ?? 0} wallet(s) don't match their ledger`}
          </div>
        </Card>
      </div>
    </div>
  );
}
