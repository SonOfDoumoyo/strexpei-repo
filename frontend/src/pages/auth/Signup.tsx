import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Check } from "lucide-react";
import { Button, cx, Input, Notice } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { useMeta } from "../../lib/queries";
import { AuthShell } from "./AuthShell";

const RULES = [
  { test: (p: string) => p.length >= 8, label: "8+ characters" },
  { test: (p: string) => /[A-Za-z]/.test(p), label: "A letter" },
  { test: (p: string) => /\d/.test(p), label: "A number" },
];

export default function Signup() {
  const navigate = useNavigate();
  const meta = useMeta();
  const [form, setForm] = useState({ first_name: "", last_name: "", email: "", phone: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const fieldError = (name: string) => (error?.details?.fields?.[name] as string | undefined) ?? null;
  const passwordOk = RULES.every((r) => r.test(form.password));

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/register", { ...form, phone: form.phone || null });
      navigate(`/verify-email?sent=${encodeURIComponent(form.email.trim())}`, { replace: true });
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle={
        <>
          {meta.data?.trial_days ? `Free for ${meta.data.trial_days} days, no card needed. ` : ""}Already have an account?{" "}
          <Link to="/login" className="font-semibold text-brand-strong hover:underline dark:text-brand">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="grid gap-5" noValidate>
        {error && !error.details?.fields && <Notice tone="bad">{error.message}</Notice>}
        <div className="grid gap-5 sm:grid-cols-2">
          <Input label="First name" autoComplete="given-name" required autoFocus value={form.first_name} onChange={set("first_name")} error={fieldError("first_name")} />
          <Input label="Last name" autoComplete="family-name" required value={form.last_name} onChange={set("last_name")} error={fieldError("last_name")} />
        </div>
        <Input label="Work email" type="email" autoComplete="email" required value={form.email} onChange={set("email")} error={fieldError("email")} hint="We'll send payroll receipts and alerts here." />
        <Input label="Phone number" type="tel" autoComplete="tel" optional placeholder="0803 123 4567" value={form.phone} onChange={set("phone")} error={fieldError("phone")} />
        <div className="grid gap-2">
          <Input label="Password" type="password" autoComplete="new-password" required value={form.password} onChange={set("password")} error={fieldError("password")} />
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {RULES.map((r) => (
              <span key={r.label} className={cx("inline-flex items-center gap-1 text-[12px]", r.test(form.password) ? "text-good" : "text-ink-3")}>
                <Check size={12} strokeWidth={3} /> {r.label}
              </span>
            ))}
          </div>
        </div>
        <Button type="submit" variant="dark" size="lg" loading={busy} disabled={!form.first_name || !form.last_name || !form.email || !passwordOk} block>
          Create account
        </Button>
        <p className="text-center text-[12px] leading-5 text-ink-3">
          Your staff don't need accounts. They join your payroll with a link and the staff ID you give them.
        </p>
      </form>
    </AuthShell>
  );
}
