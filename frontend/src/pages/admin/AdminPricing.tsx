import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, CardHeader, ErrorState, Input, MoneyInput, Notice, PageHeader, PageLoader, Textarea, Toggle } from "../../components/ui";
import { useToast } from "../../components/toast";
import { api } from "../../lib/api";
import type { Plan } from "../../lib/types";

type Settings = {
  fees: {
    commission_bps: number;
    checkout_percent_bps: number;
    checkout_flat_kobo: number;
    checkout_flat_waived_below_kobo: number;
    checkout_cap_kobo: number;
    dva_percent_bps: number;
    dva_cap_kobo: number;
    transfer_bands: { up_to_kobo: number | null; fee_kobo: number }[];
    stamp_duty_threshold_kobo: number;
    stamp_duty_kobo: number;
  };
  trial_days: number;
  trial_ai_quota: number;
  annual_discount_months: number;
  grace_days: number;
  payday_reminder_days: number;
};

function PlanEditor({ plan }: { plan: Plan }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState({ ...plan, features: plan.features.join("\n") });
  useEffect(() => setForm({ ...plan, features: plan.features.join("\n") }), [plan]);
  const save = useMutation({
    mutationFn: () =>
      api.patch<Plan>(`/admin/plans/${plan.code}`, {
        name: form.name,
        tagline: form.tagline,
        min_staff: Number(form.min_staff),
        max_staff: form.max_staff === null ? undefined : Number(form.max_staff),
        unlimited: form.max_staff === null,
        base_fee_kobo: form.base_fee_kobo,
        per_staff_kobo: form.per_staff_kobo,
        ai_monthly_quota: Number(form.ai_monthly_quota),
        features: form.features.split("\n").map((f) => f.trim()).filter(Boolean),
        active: form.active,
      }),
    onSuccess: () => {
      toast.success(`${form.name} plan saved`);
      qc.invalidateQueries({ queryKey: ["admin", "plans"] });
    },
    onError: (e) => toast.error(e),
  });
  return (
    <Card>
      <CardHeader title={form.name} description={`Code: ${plan.code}`} action={<Toggle checked={form.active} onChange={(v) => setForm({ ...form, active: v })} />} />
      <div className="grid gap-4 p-5">
        <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <Input label="Tagline" value={form.tagline ?? ""} onChange={(e) => setForm({ ...form, tagline: e.target.value })} />
        <div className="grid grid-cols-2 gap-3">
          <Input label="From (staff)" type="number" value={form.min_staff} onChange={(e) => setForm({ ...form, min_staff: Number(e.target.value) })} />
          <Input label="To (staff)" type="number" placeholder="No limit" value={form.max_staff ?? ""} onChange={(e) => setForm({ ...form, max_staff: e.target.value ? Number(e.target.value) : null })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <MoneyInput label="Base fee / month" valueKobo={form.base_fee_kobo} onChangeKobo={(v) => setForm({ ...form, base_fee_kobo: v ?? 0 })} />
          <MoneyInput label="Per staff / month" valueKobo={form.per_staff_kobo} onChangeKobo={(v) => setForm({ ...form, per_staff_kobo: v ?? 0 })} />
        </div>
        <Input label="SPI requests / month" type="number" value={form.ai_monthly_quota} onChange={(e) => setForm({ ...form, ai_monthly_quota: Number(e.target.value) })} />
        <Textarea label="Features (one per line)" value={form.features} onChange={(e) => setForm({ ...form, features: e.target.value })} />
        <div><Button loading={save.isPending} onClick={() => save.mutate()}>Save plan</Button></div>
      </div>
    </Card>
  );
}

export default function AdminPricing() {
  const toast = useToast();
  const qc = useQueryClient();
  const plans = useQuery({ queryKey: ["admin", "plans"], queryFn: () => api.get<Plan[]>("/admin/plans") });
  const settings = useQuery({ queryKey: ["admin", "settings"], queryFn: () => api.get<Settings>("/admin/settings") });
  const [form, setForm] = useState<Settings | null>(null);
  useEffect(() => {
    if (settings.data) setForm(settings.data);
  }, [settings.data]);
  const save = useMutation({
    mutationFn: () =>
      api.patch<Settings>("/admin/settings", {
        fees: form!.fees,
        trial_days: form!.trial_days,
        trial_ai_quota: form!.trial_ai_quota,
        annual_discount_months: form!.annual_discount_months,
        grace_days: form!.grace_days,
        payday_reminder_days: form!.payday_reminder_days,
      }),
    onSuccess: (s) => {
      setForm(s);
      toast.success("Platform settings saved", "New payroll runs and quotes use them immediately.");
      qc.invalidateQueries({ queryKey: ["meta"] });
    },
    onError: (e) => toast.error(e),
  });

  if (plans.isLoading || settings.isLoading || !form) return <PageLoader />;
  if (plans.error || settings.error) return <ErrorState error={plans.error ?? settings.error} />;
  const fees = form.fees;
  const setFee = (k: keyof Settings["fees"], v: number) => setForm({ ...form, fees: { ...fees, [k]: v } });

  return (
    <div>
      <PageHeader title="Pricing & fees" description="Change what Streixpei charges and mirror Paystack's current prices. Changes apply to new quotes and payroll runs." />
      <Card>
        <CardHeader title="Your fees" action={<Button loading={save.isPending} onClick={() => save.mutate()}>Save settings</Button>} />
        <div className="grid gap-5 p-5 sm:grid-cols-2 lg:grid-cols-3 sm:p-6">
          <Input label="Service fee on disbursements (%)" type="number" step="0.01" value={fees.commission_bps / 100} onChange={(e) => setFee("commission_bps", Math.round(Number(e.target.value) * 100))} hint="0.5 = 0.5% of every salary paid" />
          <Input label="Free trial (days)" type="number" value={form.trial_days} onChange={(e) => setForm({ ...form, trial_days: Number(e.target.value) })} />
          <Input label="Annual plan: free months" type="number" value={form.annual_discount_months} onChange={(e) => setForm({ ...form, annual_discount_months: Number(e.target.value) })} />
          <Input label="Grace period after expiry (days)" type="number" value={form.grace_days} onChange={(e) => setForm({ ...form, grace_days: Number(e.target.value) })} />
          <Input label="Payday reminder (days before)" type="number" value={form.payday_reminder_days} onChange={(e) => setForm({ ...form, payday_reminder_days: Number(e.target.value) })} />
          <Input label="SPI requests during trial" type="number" value={form.trial_ai_quota} onChange={(e) => setForm({ ...form, trial_ai_quota: Number(e.target.value) })} />
        </div>
        <div className="border-t border-line p-5 sm:p-6">
          <h3 className="text-[14px] font-semibold">Paystack pass-through fees</h3>
          <p className="mt-1 text-[12.5px] text-ink-3">Keep these in line with paystack.com/pricing. They're added to what managers pay so your margin is protected.</p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <Input label="Card/bank collection (%)" type="number" step="0.01" value={fees.checkout_percent_bps / 100} onChange={(e) => setFee("checkout_percent_bps", Math.round(Number(e.target.value) * 100))} />
            <MoneyInput label="Collection flat fee" valueKobo={fees.checkout_flat_kobo} onChangeKobo={(v) => setFee("checkout_flat_kobo", v ?? 0)} />
            <MoneyInput label="Flat fee waived below" valueKobo={fees.checkout_flat_waived_below_kobo} onChangeKobo={(v) => setFee("checkout_flat_waived_below_kobo", v ?? 0)} />
            <MoneyInput label="Collection fee cap" valueKobo={fees.checkout_cap_kobo} onChangeKobo={(v) => setFee("checkout_cap_kobo", v ?? 0)} />
            <Input label="Account-number transfer (%)" type="number" step="0.01" value={fees.dva_percent_bps / 100} onChange={(e) => setFee("dva_percent_bps", Math.round(Number(e.target.value) * 100))} />
            <MoneyInput label="Account-number fee cap" valueKobo={fees.dva_cap_kobo} onChangeKobo={(v) => setFee("dva_cap_kobo", v ?? 0)} />
            <MoneyInput label="Stamp duty" valueKobo={fees.stamp_duty_kobo} onChangeKobo={(v) => setFee("stamp_duty_kobo", v ?? 0)} />
            <MoneyInput label="Stamp duty from" valueKobo={fees.stamp_duty_threshold_kobo} onChangeKobo={(v) => setFee("stamp_duty_threshold_kobo", v ?? 0)} />
          </div>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {fees.transfer_bands.map((band, i) => (
              <div key={i} className="grid gap-2 rounded-2xl border border-line p-3">
                <p className="text-[12.5px] font-medium text-ink-2">Transfer band {i + 1}{band.up_to_kobo === null ? " (and above)" : ""}</p>
                {band.up_to_kobo !== null && (
                  <MoneyInput label="Up to" valueKobo={band.up_to_kobo} onChangeKobo={(v) => setForm({ ...form, fees: { ...fees, transfer_bands: fees.transfer_bands.map((b, j) => (j === i ? { ...b, up_to_kobo: v ?? 0 } : b)) } })} />
                )}
                <MoneyInput label="Fee" valueKobo={band.fee_kobo} onChangeKobo={(v) => setForm({ ...form, fees: { ...fees, transfer_bands: fees.transfer_bands.map((b, j) => (j === i ? { ...b, fee_kobo: v ?? 0 } : b)) } })} />
              </div>
            ))}
          </div>
        </div>
      </Card>

      <h2 className="mb-4 mt-10 text-[20px] font-semibold">Plans</h2>
      <Notice tone="info" className="mb-4">Plans are matched to workgroups by staff count. Keep the ranges continuous (e.g. 1–25, 26–150, 151+).</Notice>
      <div className="grid gap-6 lg:grid-cols-3">
        {(plans.data ?? []).map((p) => <PlanEditor key={p.code} plan={p} />)}
      </div>
    </div>
  );
}
