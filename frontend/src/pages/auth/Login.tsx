import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { Button, Input, Notice } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { ApiError, api } from "../../lib/api";
import { AuthShell } from "./AuthShell";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [resent, setResent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const user = await login(email, password, remember);
      const next = params.get("next");
      navigate(user.role === "admin" ? "/admin" : next && next.startsWith("/app") ? next : "/app", { replace: true });
    } catch (err) {
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    try {
      await api.post("/auth/resend-verification", { email });
      setResent(true);
    } catch (err) {
      setError(err as ApiError);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      subtitle={
        <>
          New to Streixpei?{" "}
          <Link to="/signup" className="font-semibold text-brand-strong underline-offset-2 hover:underline dark:text-brand">
            Create a free account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="grid gap-5" noValidate>
        {params.get("reset") === "1" && <Notice tone="good">Password updated. Sign in with your new password.</Notice>}
        {error && (
          <Notice
            tone={error.code === "email_not_verified" ? "warn" : "bad"}
            title={error.code === "email_not_verified" ? "Confirm your email first" : undefined}
            action={
              error.code === "email_not_verified" && !resent ? (
                <Button size="sm" variant="secondary" onClick={resend}>
                  Resend link
                </Button>
              ) : undefined
            }
          >
            {error.code === "email_not_verified" ? (resent ? "A new confirmation link is on its way." : "We've sent a fresh confirmation link to your inbox.") : error.message}
          </Notice>
        )}
        <Input label="Work email" type="email" autoComplete="email" required autoFocus value={email} onChange={(e) => setEmail(e.target.value)} />
        <Input
          label="Password"
          type={show ? "text" : "password"}
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          trailing={
            <button type="button" onClick={() => setShow((v) => !v)} className="rounded-lg p-2 text-ink-3 hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>
              {show ? <EyeOff size={17} /> : <Eye size={17} />}
            </button>
          }
        />
        <div className="flex items-center justify-between text-[13px]">
          <label className="flex cursor-pointer items-center gap-2 text-ink-2">
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} className="h-4 w-4 accent-[var(--c-brand)]" />
            Keep me signed in
          </label>
          <Link to={`/forgot-password${email ? `?email=${encodeURIComponent(email)}` : ""}`} className="font-semibold text-brand-strong hover:underline dark:text-brand">
            Forgot password?
          </Link>
        </div>
        <Button type="submit" variant="dark" size="lg" loading={busy} disabled={!email || !password} block>
          Sign in
        </Button>
      </form>
    </AuthShell>
  );
}
