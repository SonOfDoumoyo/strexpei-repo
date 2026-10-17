import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, CalendarClock, CheckCircle2, Circle, Users, Wallet } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { Badge, ButtonLink, Card, CardHeader, CopyButton, cx, EmptyState, ErrorState, PageHeader, PageLoader, Progress, Stat, StatusPill } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { date, daysUntil, dayLong, greeting, naira, plural, relative } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Overview } from "../../lib/types";

function ReadinessRow({ label, value, tone, to }: { label: string; value: number; tone: "good" | "warn" | "neutral"; to?: string }) {
  const body = (
    <span className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-[13.5px] transition hover:bg-soft/70">
      <span className="flex items-center gap-2.5">
        <span className={cx("h-2 w-2 rounded-full", tone === "good" ? "bg-good" : tone === "warn" ? "bg-warn" : "bg-ink-3")} />
        {label}
      </span>
      <span className="num font-semibold">{value}</span>
    </span>
  );
  return to ? <Link to={to}>{body}</Link> : body;
}

export default function Dashboard() {
  const workgroup = useWorkgroup();
  const { user } = useAuth();
  const q = useQuery({ queryKey: wgKey(workgroup.id, "overview"), queryFn: () => api.get<Overview>(`/workgroups/${workgroup.id}/overview`) });

  if (q.isLoading) return <PageLoader />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const d = q.data;
  const doneCount = d.checklist.filter((c) => c.done).length;
  const setupComplete = doneCount === d.checklist.length;
  const nextStep = d.checklist.find((c) => !c.done);
  const payday = d.workgroup.next_payday_at;
  const days = daysUntil(payday);
  const covered = d.estimate.total_kobo > 0 && d.wallet_balance_kobo >= d.estimate.total_kobo;

  return (
    <div>
      <PageHeader
        title={`${greeting()}, ${user?.first_name ?? ""}`}
        description={`Here's where ${d.workgroup.name} stands today.`}
        action={
          setupComplete || !nextStep ? (
            <ButtonLink to="/app/payroll" size="lg">
              Prepare payroll
            </ButtonLink>
          ) : (
            <ButtonLink to={nextStep.link} size="lg">
              Next: {nextStep.label.toLowerCase()}
            </ButtonLink>
          )
        }
      />

      {!setupComplete && (
        <Card className="mb-6 overflow-hidden">
          <div className="p-5 sm:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-[17px] font-semibold">Finish setting up</h2>
                <p className="mt-1 text-[13px] text-ink-3">
                  {doneCount} of {d.checklist.length} done — {d.checklist.length - doneCount === 1 ? "one step" : `${d.checklist.length - doneCount} steps`} left.
                </p>
              </div>
              <Progress value={doneCount} max={d.checklist.length} className="w-full sm:w-56" label="Setup progress" />
            </div>
            <ol className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
              {d.checklist.map((c, i) => (
                <li key={c.key}>
                  <Link
                    to={c.link}
                    className={cx(
                      "flex h-full items-start gap-2.5 rounded-xl border px-3 py-3 text-[13px] transition",
                      c.done ? "border-transparent text-ink-3" : c === nextStep ? "border-brand/50 bg-brand-soft/50 font-semibold" : "border-line hover:border-line-strong",
                    )}
                  >
                    {c.done ? <CheckCircle2 size={17} className="mt-px shrink-0 text-good" /> : <Circle size={17} className="mt-px shrink-0 text-ink-3" />}
                    <span>
                      <span className="mr-1 text-ink-3">{i + 1}.</span>
                      <span className={c.done ? "line-through decoration-ink-3/50" : ""}>{c.label}</span>
                    </span>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        </Card>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat
          label="Wallet balance"
          icon={<Wallet size={17} />}
          value={naira(d.wallet_balance_kobo)}
          sub={d.estimate.total_kobo === 0 ? "Fund before payday" : covered ? "Covers the next payroll" : `${naira(d.shortfall_kobo)} short of next payroll`}
          tone={!covered && d.estimate.total_kobo > 0 ? "warn" : undefined}
          action={
            <Link to="/app/wallet" className="inline-flex items-center gap-0.5 text-[12.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
              Fund <ArrowUpRight size={13} />
            </Link>
          }
        />
        <Stat
          label="Staff registered"
          icon={<Users size={17} />}
          value={
            <>
              {d.staff.registered}
              <span className="text-[16px] font-medium text-ink-3"> / {d.workgroup.headcount}</span>
            </>
          }
          sub={d.staff.pending ? `${plural(d.staff.pending, "ID")} not claimed yet` : d.staff.total ? "Every staff ID is claimed" : "No staff IDs yet"}
        />
        <Stat label="Next payroll" value={naira(d.estimate.total_kobo)} sub={`${naira(d.estimate.salaries_kobo)} salaries + ${naira(d.estimate.transfer_fees_kobo + d.estimate.commission_kobo)} fees`} />
        <Stat
          label="Next payday"
          icon={<CalendarClock size={17} />}
          value={payday ? date(payday).replace(/ \d{4}$/, "") : "—"}
          sub={`${d.workgroup.payment_mode === "automatic" ? "Automatic" : "Manual"} · ${days === null ? "" : days <= 0 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`}`}
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.25fr_1fr]">
        <div className="grid content-start gap-6">
          <Card>
            <CardHeader title="Payroll readiness" description={`Who can be paid on ${dayLong(payday)}`} action={<ButtonLink to="/app/staff" size="sm" variant="secondary">View staff</ButtonLink>} />
            <div className="grid gap-0.5 p-3">
              <ReadinessRow label="Ready to pay" value={d.staff.payout_ready} tone="good" to="/app/payroll" />
              <ReadinessRow label="Registered but missing a salary" value={d.staff.missing_salary} tone={d.staff.missing_salary ? "warn" : "neutral"} to="/app/staff?status=registered" />
              <ReadinessRow label="Bank name doesn't match their name" value={d.staff.name_mismatch} tone={d.staff.name_mismatch ? "warn" : "neutral"} to="/app/staff?attention=1" />
              <ReadinessRow label="Staff IDs not yet claimed" value={d.staff.pending} tone="neutral" to="/app/staff-ids?status=pending" />
            </div>
          </Card>

          <Card>
            <CardHeader title="Latest payroll" action={<ButtonLink to="/app/payroll" size="sm" variant="secondary">All payroll</ButtonLink>} />
            {d.last_run ? (
              <Link to={`/app/payroll/runs/${d.last_run.id}`} className="flex flex-wrap items-center justify-between gap-4 p-5 transition hover:bg-soft/40 sm:p-6">
                <div>
                  <p className="text-[15px] font-semibold">{d.last_run.period_label}</p>
                  <p className="num mt-0.5 text-[12.5px] text-ink-3">
                    {d.last_run.number} · {plural(d.last_run.staff_count, "staff member")}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-display text-[22px] font-semibold">{naira(d.last_run.total_kobo)}</p>
                  <div className="mt-1">
                    <StatusPill status={d.last_run.status} />
                  </div>
                </div>
              </Link>
            ) : (
              <EmptyState title="No payroll yet" action={<ButtonLink to="/app/payroll" size="sm">Prepare your first payroll</ButtonLink>}>
                Once staff are registered with salaries, you can pay everyone in one go.
              </EmptyState>
            )}
          </Card>
        </div>

        <div className="grid content-start gap-6">
          <Card>
            <CardHeader
              title="Onboarding link"
              description={d.workgroup.invite_active ? "Open for registrations" : "Paused — staff can't register"}
              action={<Badge tone={d.workgroup.invite_active ? "good" : "muted"}>{d.workgroup.invite_active ? "Open" : "Paused"}</Badge>}
            />
            <div className="flex items-center gap-5 p-5 sm:p-6">
              <Link to="/app/onboarding" className="shrink-0 rounded-2xl border border-line bg-white p-2.5" aria-label="Open the onboarding page">
                <QRCodeSVG value={d.workgroup.join_url} size={84} marginSize={0} fgColor="#151412" />
              </Link>
              <div className="min-w-0 flex-1">
                <p className="num truncate text-[13px] font-medium text-ink-2">{d.workgroup.join_url.replace(/^https?:\/\//, "")}</p>
                <Progress value={d.staff.registered} max={Math.max(d.workgroup.headcount, 1)} className="mt-3" label="Registration progress" />
                <p className="mt-2 text-[12.5px] text-ink-3">
                  {d.staff.registered} of {d.workgroup.headcount} registered
                </p>
                <div className="mt-3 flex gap-2">
                  <CopyButton text={d.workgroup.join_url} label="Copy link" />
                  <ButtonLink to="/app/onboarding" size="sm" variant="ghost">
                    Share
                  </ButtonLink>
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Recent activity" action={<Link to="/app/activity" className="text-[12.5px] font-semibold text-brand-strong hover:underline dark:text-brand">See all</Link>} />
            {d.activity.length ? (
              <ul className="divide-y divide-line">
                {d.activity.map((a) => (
                  <li key={a.id} className="flex gap-3 px-5 py-3.5 sm:px-6">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                    <div className="min-w-0">
                      <p className="text-[13.5px] leading-5">{a.summary}</p>
                      <p className="mt-0.5 text-[12px] text-ink-3">
                        {a.actor} · {relative(a.created_at)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="p-6 text-[13px] text-ink-3">Actions on this workgroup will show up here.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
