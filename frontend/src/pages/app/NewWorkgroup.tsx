import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, IdCard, Minus, Plus, Sparkles, Upload } from "lucide-react";
import { GenerateIds, ImportIds } from "../../components/StaffIdTools";
import { QrActions, QrCard } from "../../components/QrCard";
import { Button, Card, cx, Input, Notice, Select } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { naira, ordinal, plural } from "../../lib/format";
import { useMeta } from "../../lib/queries";
import type { Quote, Workgroup } from "../../lib/types";

const STEPS = ["Business", "Team size", "Payday", "Staff IDs", "Share"];
const INDUSTRIES = ["Retail", "Logistics & transport", "Hospitality", "Healthcare", "Education", "Manufacturing", "Construction", "Agriculture", "Technology", "Professional services", "Security", "Church / NGO", "Other"];

function useDebounced<T>(value: T, delay = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return v;
}

function Stepper({ step }: { step: number }) {
  return (
    <ol className="mb-8 flex items-center gap-2 overflow-x-auto pb-1" aria-label="Setup progress">
      {STEPS.map((label, i) => (
        <li key={label} className="flex shrink-0 items-center gap-2">
          <span
            className={cx(
              "flex h-7 w-7 items-center justify-center rounded-full text-[12px] font-bold",
              i < step ? "bg-good text-white" : i === step ? "bg-ink text-shell" : "bg-ink/8 text-ink-3",
            )}
            aria-current={i === step ? "step" : undefined}
          >
            {i < step ? <Check size={14} strokeWidth={3} /> : i + 1}
          </span>
          <span className={cx("text-[13px] font-medium", i === step ? "text-ink" : "text-ink-3")}>{label}</span>
          {i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-line-strong sm:w-10" />}
        </li>
      ))}
    </ol>
  );
}

export default function NewWorkgroup() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const meta = useMeta();
  const { select, workgroups } = useWorkgroups();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ name: "", address: "", industry: "", headcount: 10, payment_mode: "manual" as "manual" | "automatic", payday_day: 25, payday_time: "09:00" });
  const [created, setCreated] = useState<Workgroup | null>(null);
  const [idChoice, setIdChoice] = useState<"have" | "generate" | null>(null);
  const [idsDone, setIdsDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const seats = useDebounced(form.headcount);
  const quote = useQuery({
    queryKey: ["quote", seats],
    queryFn: () => api.get<Quote>("/pricing/quote", { seats }),
    enabled: seats >= 1,
    placeholderData: (prev) => prev,
  });

  const setHeadcount = (n: number) => setForm((f) => ({ ...f, headcount: Math.max(1, Math.min(5000, Math.round(n) || 1)) }));

  async function create() {
    setBusy(true);
    setError(null);
    try {
      const wg = await api.post<Workgroup>("/workgroups", { ...form, address: form.address || null, industry: form.industry || null });
      setCreated(wg);
      await qc.invalidateQueries({ queryKey: ["workgroups"] });
      select(wg.id);
      setStep(3);
      toast.success(`${wg.name} is ready`, "Next, set up the staff IDs your team will register with.");
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6">
        <h1 className="text-[30px] font-semibold leading-tight sm:text-[34px]">{workgroups.length ? "New workgroup" : "Set up your first workgroup"}</h1>
        <p className="mt-2 max-w-xl text-[14px] leading-6 text-ink-2">
          A workgroup is a business or branch whose staff you pay together. It gets its own staff IDs, onboarding link, wallet and payday.
        </p>
      </div>
      <Stepper step={step} />

      {step === 0 && (
        <Card className="p-6 sm:p-8">
          <div className="grid gap-5">
            <Input label="Business name" autoFocus placeholder="e.g. Acme Logistics Ltd" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} hint="Staff see this name when they register." />
            <Input label="Address" optional placeholder="12 Marina Road, Lagos" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            <Select label="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
              <option value="">Choose one (optional)</option>
              {INDUSTRIES.map((i) => (
                <option key={i}>{i}</option>
              ))}
            </Select>
          </div>
          <div className="mt-8 flex justify-end">
            <Button size="lg" disabled={form.name.trim().length < 2} onClick={() => setStep(1)}>
              Continue
            </Button>
          </div>
        </Card>
      )}

      {step === 1 && (
        <Card className="p-6 sm:p-8">
          <h2 className="text-[19px] font-semibold">How many staff will you pay?</h2>
          <p className="mt-1 text-[13.5px] leading-6 text-ink-2">Each staff member uses one seat and one staff ID. Your plan and price follow this number, and you can change it any time.</p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <div className="flex items-center rounded-2xl border border-line bg-raised">
              <button type="button" aria-label="Fewer staff" onClick={() => setHeadcount(form.headcount - 1)} className="flex h-14 w-12 items-center justify-center text-ink-2 hover:text-ink">
                <Minus size={18} />
              </button>
              <input
                type="number"
                min={1}
                max={5000}
                aria-label="Number of staff"
                value={form.headcount}
                onChange={(e) => setHeadcount(Number(e.target.value))}
                className="num h-14 w-24 bg-transparent text-center font-display text-[28px] font-semibold outline-none"
              />
              <button type="button" aria-label="More staff" onClick={() => setHeadcount(form.headcount + 1)} className="flex h-14 w-12 items-center justify-center text-ink-2 hover:text-ink">
                <Plus size={18} />
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {[10, 25, 50, 100, 250].map((n) => (
                <button key={n} type="button" onClick={() => setHeadcount(n)} className={cx("num h-9 rounded-xl border px-3 text-[13px] font-semibold transition", form.headcount === n ? "border-brand bg-brand-soft" : "border-line bg-raised hover:border-line-strong")}>
                  {n}
                </button>
              ))}
            </div>
          </div>
          {quote.data && (
            <div className="mt-6 rounded-2xl border border-line bg-soft/50 p-5">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-[14px] font-semibold">
                  {quote.data.plan.name} plan <span className="font-normal text-ink-3">· {plural(form.headcount, "staff member")}</span>
                </p>
                <p className="font-display text-[24px] font-semibold">
                  {naira(quote.data.monthly_kobo)}
                  <span className="text-[13px] font-normal text-ink-3"> / month</span>
                </p>
              </div>
              <p className="mt-2 text-[13px] leading-6 text-ink-2">
                {naira(quote.data.plan.base_fee_kobo)} base + {naira(quote.data.plan.per_staff_kobo)} per staff. Plus a {quote.data.commission_label} service fee on salaries you disburse, and Paystack's transfer fees.
              </p>
              {meta.data?.trial_days ? (
                <p className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-brand-soft px-2.5 py-1 text-[12.5px] font-semibold text-brand-strong dark:text-brand">
                  <Sparkles size={13} /> First {meta.data.trial_days} days free — no card needed
                </p>
              ) : null}
            </div>
          )}
          <div className="mt-8 flex justify-between">
            <Button variant="ghost" onClick={() => setStep(0)}>
              Back
            </Button>
            <Button size="lg" onClick={() => setStep(2)}>
              Continue
            </Button>
          </div>
        </Card>
      )}

      {step === 2 && (
        <Card className="p-6 sm:p-8">
          <h2 className="text-[19px] font-semibold">How should payday work?</h2>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {(
              [
                ["manual", "Manual", "Each payday you review payroll, then pay by bank transfer to an account number or by card. Nothing moves until you disburse."],
                ["automatic", "Automatic", "Keep the wallet funded and Streixpei pays everyone on payday. If funds are short, we email you how much to add."],
              ] as const
            ).map(([value, title, text]) => (
              <button
                key={value}
                type="button"
                onClick={() => setForm({ ...form, payment_mode: value })}
                aria-pressed={form.payment_mode === value}
                className={cx("rounded-2xl border p-5 text-left transition", form.payment_mode === value ? "border-brand bg-brand-soft/60 ring-4 ring-glow" : "border-line bg-raised hover:border-line-strong")}
              >
                <span className="flex items-center justify-between">
                  <span className="text-[15px] font-semibold">{title}</span>
                  <span className={cx("flex h-5 w-5 items-center justify-center rounded-full border", form.payment_mode === value ? "border-brand bg-brand text-brand-ink" : "border-line-strong")}>
                    {form.payment_mode === value && <Check size={12} strokeWidth={3} />}
                  </span>
                </span>
                <span className="mt-2 block text-[13px] leading-6 text-ink-2">{text}</span>
              </button>
            ))}
          </div>
          <div className="mt-6 grid gap-5 sm:grid-cols-2">
            <Select label="Payday" value={form.payday_day} onChange={(e) => setForm({ ...form, payday_day: Number(e.target.value) })} hint="Months without that day use their last day.">
              {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>
                  {d === 31 ? "Last day of the month" : `${ordinal(d)} of every month`}
                </option>
              ))}
            </Select>
            <Select label="Time (Lagos)" value={form.payday_time} onChange={(e) => setForm({ ...form, payday_time: e.target.value })}>
              {["06:00", "07:00", "08:00", "09:00", "10:00", "12:00", "15:00", "18:00"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </Select>
          </div>
          {error && <Notice tone="bad" className="mt-5">{error}</Notice>}
          <div className="mt-8 flex justify-between">
            <Button variant="ghost" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button size="lg" loading={busy} onClick={create}>
              Create workgroup
            </Button>
          </div>
        </Card>
      )}

      {step === 3 && created && (
        <Card className="p-6 sm:p-8">
          <h2 className="text-[19px] font-semibold">Do you already give your staff IDs?</h2>
          <p className="mt-1 text-[13.5px] leading-6 text-ink-2">
            Staff enter their ID on the onboarding form. Only IDs on this list can register, and each ID can be used once — that's how we know every registration is genuine.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            {(
              [
                ["have", Upload, "Yes, upload our IDs", "Use the employee numbers you already have — from Excel, CSV, or pasted."],
                ["generate", IdCard, "No, create IDs for me", `We'll generate ${plural(created.headcount, "unique ID")} you can download and hand out.`],
              ] as const
            ).map(([value, Icon, title, text]) => (
              <button
                key={value}
                type="button"
                onClick={() => setIdChoice(value)}
                aria-pressed={idChoice === value}
                className={cx("flex gap-4 rounded-2xl border p-5 text-left transition", idChoice === value ? "border-brand bg-brand-soft/60 ring-4 ring-glow" : "border-line bg-raised hover:border-line-strong")}
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-soft text-brand-strong dark:text-brand">
                  <Icon size={19} />
                </span>
                <span>
                  <span className="block text-[15px] font-semibold">{title}</span>
                  <span className="mt-1 block text-[13px] leading-6 text-ink-2">{text}</span>
                </span>
              </button>
            ))}
          </div>
          {idChoice && (
            <div className="mt-6 border-t border-line pt-6">
              {idChoice === "have" ? <ImportIds workgroup={created} onDone={(r) => r.report.added_count > 0 && setIdsDone(true)} /> : <GenerateIds workgroup={created} remaining={created.headcount} onDone={() => setIdsDone(true)} />}
            </div>
          )}
          <div className="mt-8 flex flex-wrap justify-between gap-2">
            <Button variant="ghost" onClick={() => setStep(4)}>
              Skip for now
            </Button>
            <Button size="lg" disabled={!idsDone} onClick={() => setStep(4)}>
              Continue
            </Button>
          </div>
        </Card>
      )}

      {step === 4 && created && (
        <Card className="p-6 sm:p-8">
          <div className="grid items-center gap-8 md:grid-cols-[auto_1fr]">
            <QrCard workgroup={created} size={176} actions={false} />
            <div>
              <h2 className="text-[22px] font-semibold">Share this with your staff</h2>
              <p className="mt-2 text-[13.5px] leading-6 text-ink-2">
                Staff scan the code or open the link, enter their staff ID, and add their bank details. We verify each account with the bank before saving it — no Streixpei account needed.
              </p>
              <p className="num mt-4 break-all rounded-xl bg-soft px-3 py-2.5 text-[13px] font-medium">{created.join_url}</p>
            </div>
          </div>
          <div className="mt-6 border-t border-line pt-6">
            <QrActions workgroup={created} />
          </div>
          <div className="mt-8 flex justify-end">
            <Button size="lg" onClick={() => navigate("/app")}>
              Go to dashboard
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
