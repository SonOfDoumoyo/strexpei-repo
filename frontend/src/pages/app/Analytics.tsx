import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart, DataTableToggle, HBars, LineChart } from "../../components/charts";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, PageLoader, Segmented, Stat, Table, Td, Th } from "../../components/ui";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { monthLabel, naira, nairaCompact, plural } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Analytics as AnalyticsData } from "../../lib/types";

export default function Analytics() {
  const workgroup = useWorkgroup();
  const [months, setMonths] = useState<"6" | "12" | "24">("12");
  const q = useQuery({ queryKey: wgKey(workgroup.id, "analytics", months), queryFn: () => api.get<AnalyticsData>(`/workgroups/${workgroup.id}/analytics`, { months }) });

  if (q.isLoading) return <PageLoader />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const t = d.totals;
  const hasPayments = t.payments_count > 0;
  const change = t.month_change_pct;

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="What you've paid, how your team has grown, and where payroll money goes."
        action={<Segmented value={months} onChange={setMonths} options={[{ value: "6", label: "6 months" }, { value: "12", label: "12 months" }, { value: "24", label: "24 months" }]} />}
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Paid to staff, all time" value={nairaCompact(t.lifetime_paid_kobo)} sub={plural(t.payments_count, "payment")} />
        <Stat label="Current monthly payroll" value={nairaCompact(t.monthly_payroll_kobo)} sub={`Average salary ${naira(t.average_salary_kobo)}`} />
        <Stat
          label="Change vs last month"
          value={change === null ? "—" : `${change > 0 ? "+" : ""}${change}%`}
          sub="Salaries paid this month"
        />
        <Stat label="Transfer success rate" value={t.success_rate === null ? "—" : `${t.success_rate}%`} sub={t.failed_count ? `${plural(t.failed_count, "failed transfer")}, refunded` : "No failed transfers"} />
      </div>

      <Card className="mt-6">
        <CardHeader title="Salaries paid per month" description="Successful transfers to staff, by the month they landed" />
        <div className="p-5 sm:p-6">
          {hasPayments ? (
            <DataTableToggle
              table={
                <Table>
                  <thead><tr><Th>Month</Th><Th align="right">Salaries</Th><Th align="right">Fees</Th><Th align="right">Staff paid</Th></tr></thead>
                  <tbody>
                    {d.series.map((s) => (
                      <tr key={s.month}><Td>{s.month}</Td><Td align="right">{naira(s.salaries_kobo)}</Td><Td align="right">{naira(s.fees_kobo)}</Td><Td align="right">{s.staff_paid}</Td></tr>
                    ))}
                  </tbody>
                </Table>
              }
            >
              <BarChart
                label="Salaries paid per month"
                format={nairaCompact}
                data={d.series.map((s) => ({
                  key: s.month,
                  label: monthLabel(s.month),
                  values: [s.salaries_kobo],
                  detail: (
                    <>
                      <p className="num text-ink">{naira(s.salaries_kobo)}</p>
                      <p className="text-ink-3">{plural(s.staff_paid, "staff member")} · fees {naira(s.fees_kobo)}</p>
                    </>
                  ),
                }))}
              />
            </DataTableToggle>
          ) : (
            <EmptyState title="No payments yet">Once you disburse payroll, monthly totals show up here.</EmptyState>
          )}
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Registered staff" description="Total staff registered by the end of each month" />
          <div className="p-5 sm:p-6">
            <LineChart label="Registered staff over time" format={(v) => String(Math.round(v))} data={d.headcount.map((h) => ({ key: h.month, label: monthLabel(h.month), value: h.registered }))} />
          </div>
        </Card>
        <Card>
          <CardHeader title="Monthly payroll by role" description="Current salaries of registered staff" />
          <div className="p-5 sm:p-6">
            {d.by_role.length ? (
              <HBars label="Monthly payroll by role" format={naira} rows={d.by_role.map((r) => ({ label: r.role, value: r.salaries_kobo, sub: `· ${plural(r.staff, "person", "people")}` }))} />
            ) : (
              <p className="text-[13px] text-ink-3">Register staff and set salaries to see the breakdown.</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
