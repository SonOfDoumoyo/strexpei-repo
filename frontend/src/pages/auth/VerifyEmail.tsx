import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { MailCheck } from "lucide-react";
import { Button, Input, Notice, Spinner } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { ApiError, api } from "../../lib/api";
import type { User } from "../../lib/types";
import { AuthShell } from "./AuthShell";

export default function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const sentTo = params.get("sent");
  const { startSession } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState(sentTo ?? "");
  const [resent, setResent] = useState(false);
  const [busy, setBusy] = useState(false);
  const ran = useRef(false);

  useEffect(() => {
    if (!token || ran.current) return;
    ran.current = true;
    api
      .post<{ access_token: string; user: User }>("/auth/verify-email", { token })
      .then((payload) => {
        startSession(payload);
        navigate(payload.user.workgroup_count ? "/app" : "/app/workgroups/new", { replace: true });
      })
      .catch((err: ApiError) => setError(err.message));
  }, [token, startSession, navigate]);

  async function resend() {
    setBusy(true);
    try {
      await api.post("/auth/resend-verification", { email });
      setResent(true);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  if (token && !error) {
    return (
      <AuthShell title="Confirming your email">
        <div className="flex items-center gap-3 text-ink-2">
          <Spinner /> One moment…
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={error ? "That link didn't work" : "Check your inbox"}
      subtitle={
        error ? (
          "Confirmation links expire after 24 hours and work once. Request a new one below."
        ) : (
          <>
            We sent a confirmation link to <strong className="text-ink">{sentTo ?? "your email"}</strong>. Open it on this device to finish setting up.
          </>
        )
      }
    >
      <div className="grid gap-5">
        {!error && (
          <div className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-4">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-soft text-brand-strong dark:text-brand">
              <MailCheck size={20} />
            </span>
            <p className="text-[13.5px] leading-6 text-ink-2">Can't find it? Check spam or promotions, or send it again.</p>
          </div>
        )}
        {error && <Notice tone="bad">{error}</Notice>}
        {resent && <Notice tone="good">A new link is on its way to {email}.</Notice>}
        <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button variant="dark" size="lg" block loading={busy} disabled={!email} onClick={resend}>
          Send a new link
        </Button>
        <Link to="/login" className="text-center text-[13.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
          Back to sign in
        </Link>
      </div>
    </AuthShell>
  );
}
