import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Input, Notice } from "../../components/ui";
import { ApiError, api } from "../../lib/api";
import { AuthShell } from "./AuthShell";

export default function ForgotPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [step, setStep] = useState<"email" | "code">("email");
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  async function requestCode(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ message: string }>("/auth/forgot-password", { email });
      setInfo(res.message);
      setStep("code");
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function reset(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/auth/reset-password", { email, otp, password });
      navigate(`/login?reset=1&email=${encodeURIComponent(email)}`, { replace: true });
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.details?.fields?.password ?? apiErr.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title={step === "email" ? "Reset your password" : "Enter your code"}
      subtitle={step === "email" ? "We'll email you a 6-digit code." : <>We sent a code to <strong className="text-ink">{email}</strong>. It expires in 10 minutes.</>}
    >
      {step === "email" ? (
        <form onSubmit={requestCode} className="grid gap-5">
          {error && <Notice tone="bad">{error}</Notice>}
          <Input label="Email" type="email" autoComplete="email" autoFocus required value={email} onChange={(e) => setEmail(e.target.value)} />
          <Button type="submit" variant="dark" size="lg" block loading={busy} disabled={!email}>
            Send code
          </Button>
          <Link to="/login" className="text-center text-[13.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
            Back to sign in
          </Link>
        </form>
      ) : (
        <form onSubmit={reset} className="grid gap-5">
          {info && !error && <Notice tone="info">{info}</Notice>}
          {error && <Notice tone="bad">{error}</Notice>}
          <Input
            label="6-digit code"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            autoFocus
            className="num text-center text-[20px] font-semibold tracking-[0.4em]"
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 6))}
          />
          <Input label="New password" type="password" autoComplete="new-password" hint="At least 8 characters with a letter and a number." value={password} onChange={(e) => setPassword(e.target.value)} />
          <Button type="submit" variant="dark" size="lg" block loading={busy} disabled={otp.length !== 6 || password.length < 8}>
            Update password
          </Button>
          <button type="button" onClick={() => requestCode()} className="text-center text-[13px] font-medium text-ink-3 hover:text-ink">
            Didn't get it? Send a new code
          </button>
        </form>
      )}
    </AuthShell>
  );
}
