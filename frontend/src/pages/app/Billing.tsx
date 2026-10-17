import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { Button, Card, CardHeader, cx, EmptyState, ErrorState, Input, KeyValue, Modal, Notice, PageHeader, PageLoader, Segmented, StatusPill, Table, Td, Th, Toggle } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup, useWorkgroups } from "../../context/workgroup";
import { useAuth } from "../../context/auth";
import { ApiError, api } from "../../lib/api";
import { date, naira, plural } from "../../lib/format";
import { useMeta, wgKey } from "../../lib/queries";
import type { BillingInfo, Invoice, Payment, Plan, Quote } from "../../lib/types";

type PayResult = { invoice: Invoice; payment: Payment | null; paid: boolean };

function planPrice(plan: Plan, seats: number) {
  return plan.base_fee_kobo + plan.per_staff_kobo * seats;
}

function SubscribeModal({ info, onClose }: { info: BillingInfo; onClose: () => void }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const { refresh } = useWorkgroups();
  const { reloadUser } = useAuth();
  const [seats, setSeats] = useState(String(Math.max(info.subscription?.seats ?? workgroup.headcount, info.seats_in_use)));
  const [cycle, setCycle] = useState<"monthly" | "annual">(info.subscription?.billing_cycle ?? "monthly");
  const [payWith, setPayWith] = useState<"checkout" | "wallet">("checkout");
  const n = Math.max(1, Number(seats) || 1);
  const quote = useQuery({ queryKey: ["quote", n, cycle], queryFn: () => api.get<Quote>("/pricing/quote", { seats: n, cycle }), placeholderData: (p) => p });
  const pay = useMutation({
    mutationFn: () => api.post<PayResult>(`/workgroups/${workgroup.id}/billing/subscribe`, { seats: n, billing_cycle: cycle, pay_with: payWith }),
    onSuccess: async (r) => {
      if (r.payment?.authorization_url) {
        window.location.href = r.payment.authorization_url;
        return;
      }
      toast.success("Subscription active", `${r.invoice.number} paid from your wallet.`);
      await Promise.all([refresh(), reloadUser()]);
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      onClose();
    },
  });
  const err = pay.error as ApiError | null;
  const amount = quote.data?.amount_kobo ?? 0;
  return (
    <Modal
      open
      onClose={onClose}
      title={info.subscription?.status === "active" ? "Renew early" : "Choose your plan"}
      description="Your plan is set by the number of staff you pay. Bigger teams pay less per person."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={pay.isPending} disabled={n < info.seats_in_use || (payWith === "wallet" && info.wallet_balance_kobo < amount)} onClick={() => pay.mutate()}>
            {payWith === "wallet" ? `Pay ${naira(amount)} from wallet` : `Pay ${naira(amount)}`}
          </Button>
        </>
      }
    >
      <div className="grid gap-5">
        <Input label="Staff seats" type="number" min={info.seats_in_use || 1} className="num" value={seats} onChange={(e) => setSeats(e.target.value)} hint={`You have ${plural(info.seats_in_use, "staff ID")} in use.`} error={n < info.seats_in_use ? `Choose at least ${info.seats_in_use}.` : null} />
        <div className="grid gap-1.5">
          <span className="text-[13px] font-medium">Billing</span>
          <Segmented
            value={cycle}
            onChange={setCycle}
            options={[
              { value: "monthly", label: "Monthly" },
              { value: "annual", label: `Yearly — ${quote.data && cycle === "annual" ? `${12 - quote.data.months_charged} months free` : "save more"}` },
            ]}
          />
        </div>
        {quote.data && (
          <div className="rounded-2xl border border-line bg-soft/50 p-4">
            <div className="flex items-baseline justify-between">
              <span className="text-[14px] font-semibold">{quote.data.plan.name} plan</span>
              <span className="font-display text-[24px] font-semibold">{naira(amount)}</span>
            </div>
            <p className="mt-1 text-[12.5px] text-ink-3">
              {naira(quote.data.monthly_kobo)}/month × {quote.data.months_charged} month{quote.data.months_charged > 1 ? "s" : ""}
              {quote.data.months_covered > quote.data.months_charged ? ` — covers ${quote.data.months_covered} months` : ""}
            </p>
          </div>
        )}
        <div className="grid gap-1.5">
          <span className="text-[13px] font-medium">Pay with</span>
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["checkout", "Card or transfer", "Via Paystack"],
                ["wallet", "Workgroup wallet", `Balance ${naira(info.wallet_balance_kobo)}`],
              ] as const
            ).map(([v, title, sub]) => (
              <button key={v} type="button" aria-pressed={payWith === v} onClick={() => setPayWith(v)} className={cx("rounded-xl border px-3 py-2.5 text-left transition", payWith === v ? "border-brand bg-brand-soft/60" : "border-line hover:border-line-strong")}>
                <span className="block text-[13.5px] font-semibold">{title}</span>
                <span className="block text-[12px] text-ink-3">{sub}</span>
              </button>
            ))}
          </div>
          {payWith === "wallet" && info.wallet_balance_kobo < amount && <p className="text-[12.5px] text-warn">Your wallet doesn't cover this. Top it up or pay by card.</p>}
        </div>
        {err && <Notice tone="bad">{err.message}</Notice>}
      </div>
    </Modal>
  );
}

function SeatsCard({ info, highlight }: { info: BillingInfo; highlight: boolean }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const { refresh } = useWorkgroups();
  const ref = useRef<HTMLDivElement>(null);
  const current = info.subscription?.seats ?? workgroup.headcount;
  const [seats, setSeats] = useState(String(current));
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  useEffect(() => {
    if (highlight) ref.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlight]);
  const n = Number(seats) || 0;
  const change = useMutation({
    mutationFn: () => api.post<{ applied: boolean; invoice: Invoice | null }>(`/workgroups/${workgroup.id}/billing/seats`, { seats: n }),
    onSuccess: async (r) => {
      if (r.applied) {
        toast.success(`Staff count set to ${n}`);
        await refresh();
        qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      } else setInvoice(r.invoice);
    },
    onError: (e) => toast.error(e),
  });
  const pay = useMutation({
    mutationFn: (payWith: "wallet" | "checkout") => api.post<PayResult>(`/workgroups/${workgroup.id}/billing/invoices/${invoice!.id}/pay`, { pay_with: payWith }),
    onSuccess: async (r) => {
      if (r.payment?.authorization_url) {
        window.location.href = r.payment.authorization_url;
        return;
      }
      toast.success(`Staff count set to ${r.invoice.seats}`);
      setInvoice(null);
      await refresh();
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
    },
    onError: (e) => toast.error(e),
  });
  const activePeriod = info.subscription?.status === "active";
  return (
    <div ref={ref}>
      <Card className={cx(highlight && "ring-4 ring-glow")}>
        <CardHeader title="Staff count" description={`${plural(info.seats_in_use, "seat")} in use of ${current}`} />
        <div className="grid gap-4 p-5 sm:p-6">
          <div className="flex flex-wrap items-end gap-3">
            <Input label="Seats" type="number" min={Math.max(1, info.seats_in_use)} className="num w-32" value={seats} onChange={(e) => setSeats(e.target.value)} />
            <Button className="mb-0" variant="dark" disabled={!n || n === current || n < info.seats_in_use} loading={change.isPending} onClick={() => change.mutate()}>
              Update
            </Button>
          </div>
          <p className="text-[12.5px] leading-5 text-ink-3">
            {activePeriod
              ? "Adding seats costs the prorated difference for the rest of this period. Fewer seats take effect now; the lower price applies at renewal."
              : "Changes apply immediately. Your price at checkout follows the new count."}
          </p>
          {invoice && (
            <div className="grid gap-3 rounded-2xl border border-brand/40 bg-brand-soft/50 p-4">
              <p className="text-[13.5px] font-semibold">{invoice.description}</p>
              <p className="font-display text-[22px] font-semibold">{naira(invoice.amount_kobo)}</p>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" loading={pay.isPending && pay.variables === "checkout"} onClick={() => pay.mutate("checkout")}>Pay by card or transfer</Button>
                <Button size="sm" variant="secondary" disabled={info.wallet_balance_kobo < invoice.amount_kobo} loading={pay.isPending && pay.variables === "wallet"} onClick={() => pay.mutate("wallet")}>
                  Pay from wallet
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

export default function Billing() {
  const workgroup = useWorkgroup();
  const { refresh } = useWorkgroups();
  const toast = useToast();
  const meta = useMeta();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [subscribing, setSubscribing] = useState(false);
  const [calc, setCalc] = useState(workgroup.headcount);
  const q = useQuery({ queryKey: wgKey(workgroup.id, "billing"), queryFn: () => api.get<BillingInfo>(`/workgroups/${workgroup.id}/billing`) });
  const autoRenew = useMutation({
    mutationFn: (v: boolean) => api.patch(`/workgroups/${workgroup.id}`, { auto_renew: v }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: wgKey(workgroup.id, "billing") });
      void refresh();
    },
    onError: (e) => toast.error(e),
  });
  const payInvoice = useMutation({
    mutationFn: ({ id, payWith }: { id: string; payWith: "wallet" | "checkout" }) => api.post<PayResult>(`/workgroups/${workgroup.id}/billing/invoices/${id}/pay`, { pay_with: payWith }),
    onSuccess: async (r) => {
      if (r.payment?.authorization_url) window.location.href = r.payment.authorization_url;
      else {
        toast.success("Invoice paid");
        await refresh();
        qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      }
    },
    onError: (e) => toast.error(e),
  });

  if (q.isLoading) return <PageLoader />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const info = q.data;
  const sub = info.subscription;
  const canSubscribe = !sub || sub.status !== "active" || (sub.days_left !== null && sub.days_left <= 7);

  return (
    <div>
      <PageHeader title="Plan & billing" description="One subscription per workgroup, priced by how many staff you pay." />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-4 p-6 sm:p-7">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-[24px] font-semibold">{sub?.status === "trialing" ? "Free trial" : `${sub?.plan.name ?? "No"} plan`}</h2>
                {sub && <StatusPill status={sub.status} />}
              </div>
              <p className="mt-1 text-[13.5px] text-ink-2">
                {sub?.status === "trialing"
                  ? `Everything included until ${date(sub.trial_ends_at)}${sub.days_left !== null ? ` — ${plural(sub.days_left, "day")} left` : ""}.`
                  : sub?.status === "active"
                    ? `Renews ${date(sub.current_period_end)} for ${naira(sub.renewal_amount_kobo)}.`
                    : sub?.status === "past_due"
                      ? `Payment was due ${date(sub.current_period_end)}. Pay now to keep payroll running.`
                      : "Subscribe to onboard staff and run payroll."}
              </p>
            </div>
            {canSubscribe && (
              <Button size="lg" onClick={() => setSubscribing(true)}>
                {sub?.status === "active" ? "Renew early" : sub?.status === "trialing" ? "Subscribe now" : "Choose a plan"}
              </Button>
            )}
          </div>
          {sub && (
            <div className="grid gap-6 border-t border-line p-6 sm:grid-cols-2 sm:p-7">
              <KeyValue
                rows={[
                  ["Plan", `${sub.plan.name} (${sub.plan.min_staff}${sub.plan.max_staff ? `–${sub.plan.max_staff}` : "+"} staff)`],
                  ["Seats", `${info.seats_in_use} used of ${sub.seats}`],
                  ["Price", `${naira(sub.monthly_kobo)} / month`],
                  ["Billing", sub.billing_cycle === "annual" ? "Yearly" : "Monthly"],
                ]}
              />
              <div className="grid content-start gap-4">
                <Toggle
                  checked={sub.auto_renew}
                  disabled={autoRenew.isPending}
                  onChange={(v) => autoRenew.mutate(v)}
                  label="Renew from wallet"
                  description="When the period ends we take the renewal from this workgroup's wallet. If it's short, we email you."
                />
                <p className="text-[12.5px] leading-5 text-ink-3">
                  On top of the plan: a {meta.data?.commission_label ?? "0.5%"} service fee on salaries you disburse, plus Paystack's transfer fee for each staff payment.
                </p>
              </div>
            </div>
          )}
        </Card>
        <SeatsCard info={info} highlight={params.get("seats") === "1"} />
      </div>

      <section className="mt-10">
        <div className="mb-5 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <h2 className="text-[22px] font-semibold">Plans</h2>
            <p className="mt-1 text-[13.5px] text-ink-2">Your plan follows your staff count automatically.</p>
          </div>
          <label className="flex items-center gap-3 text-[13px] font-medium">
            <span className="num w-24 text-right">{plural(calc, "staff", "staff")}</span>
            <input type="range" min={1} max={500} value={calc} onChange={(e) => setCalc(Number(e.target.value))} className="w-56 accent-[var(--c-brand)]" aria-label="Staff count for price comparison" />
          </label>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {info.plans.map((plan) => {
            const fits = calc >= plan.min_staff && (plan.max_staff === null || calc <= plan.max_staff);
            const current = sub?.plan.code === plan.code && sub.status !== "trialing";
            return (
              <Card key={plan.code} className={cx("flex flex-col p-6", fits && "ring-2 ring-brand/60")}>
                <div className="flex items-center justify-between">
                  <h3 className="text-[18px] font-semibold">{plan.name}</h3>
                  {current ? <StatusPill status="active" label="Current" /> : fits ? <span className="text-[12px] font-semibold text-brand-strong dark:text-brand">Fits {calc} staff</span> : null}
                </div>
                <p className="mt-1 min-h-[40px] text-[13px] leading-5 text-ink-3">{plan.tagline}</p>
                <p className="mt-5 font-display text-[28px] font-semibold">
                  {naira(plan.per_staff_kobo)}
                  <span className="text-[13px] font-normal text-ink-3"> / staff / month</span>
                </p>
                <p className="text-[12.5px] text-ink-3">+ {naira(plan.base_fee_kobo)} base fee</p>
                {fits && <p className="mt-3 rounded-lg bg-soft px-3 py-2 text-[13px]">For {calc} staff: <strong className="num">{naira(planPrice(plan, calc))}</strong> / month</p>}
                <ul className="mt-5 grid gap-2 text-[13px] text-ink-2">
                  {plan.features.map((f) => (
                    <li key={f} className="flex gap-2">
                      <Check size={15} className="mt-0.5 shrink-0 text-brand-strong dark:text-brand" />
                      {f}
                    </li>
                  ))}
                </ul>
              </Card>
            );
          })}
        </div>
      </section>

      <Card className="mt-10 overflow-hidden">
        <CardHeader title="Invoices" />
        {info.invoices.length === 0 ? (
          <EmptyState title="No invoices yet">Subscription payments and receipts appear here.</EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Invoice</Th>
                <Th>Covers</Th>
                <Th align="right">Amount</Th>
                <Th>Status</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {info.invoices.map((i) => (
                <tr key={i.id}>
                  <Td>
                    <p className="num font-medium">{i.number}</p>
                    <p className="text-[12px] text-ink-3">{i.description}</p>
                  </Td>
                  <Td className="text-ink-2">{date(i.period_start)} – {date(i.period_end)}</Td>
                  <Td align="right" className="font-medium">{naira(i.amount_kobo)}</Td>
                  <Td>
                    <StatusPill status={i.status} />
                    {i.paid_at && <p className="mt-0.5 text-[12px] text-ink-3">{date(i.paid_at)} · {i.paid_via}</p>}
                  </Td>
                  <Td align="right">
                    {i.status === "pending" && (
                      <div className="flex justify-end gap-2">
                        <Button size="sm" loading={payInvoice.isPending} onClick={() => payInvoice.mutate({ id: i.id, payWith: "checkout" })}>Pay</Button>
                        <Button size="sm" variant="secondary" disabled={info.wallet_balance_kobo < i.amount_kobo} onClick={() => payInvoice.mutate({ id: i.id, payWith: "wallet" })}>From wallet</Button>
                      </div>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      {subscribing && <SubscribeModal info={info} onClose={() => setSubscribing(false)} />}
    </div>
  );
}
