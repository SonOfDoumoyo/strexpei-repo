import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { ButtonLink, Card, Spinner } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { naira } from "../../lib/format";
import type { Payment } from "../../lib/types";

export default function PaymentCallback() {
  const [params] = useSearchParams();
  const reference = params.get("reference") ?? params.get("trxref") ?? "";
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tries, setTries] = useState(0);
  const qc = useQueryClient();
  const { refresh } = useWorkgroups();
  const { reloadUser } = useAuth();
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!reference) return;
    let alive = true;
    api
      .post<Payment>(`/payments/${encodeURIComponent(reference)}/verify`)
      .then(async (p) => {
        if (!alive) return;
        setPayment(p);
        if (p.status === "success") {
          qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "wg" });
          await Promise.all([refresh(), reloadUser()]);
        } else if (p.status === "pending" && tries < 8) {
          timer.current = window.setTimeout(() => setTries((t) => t + 1), 3000);
        }
      })
      .catch((e: ApiError) => alive && setError(e.message));
    return () => {
      alive = false;
      window.clearTimeout(timer.current);
    };
  }, [reference, tries, qc, refresh, reloadUser]);

  const next =
    payment?.purpose === "payroll" && payment.payroll_run_id
      ? { to: `/app/payroll/runs/${payment.payroll_run_id}`, label: payment.status === "success" ? "Continue to disburse" : "Back to payroll" }
      : payment?.purpose === "invoice"
        ? { to: "/app/billing", label: "View billing" }
        : { to: "/app/wallet", label: "Go to wallet" };

  return (
    <div className="mx-auto max-w-lg py-10">
      <Card className="p-8 text-center">
        {!reference ? (
          <p className="text-ink-2">No payment reference was provided.</p>
        ) : error ? (
          <>
            <XCircle size={40} className="mx-auto text-bad" />
            <h1 className="mt-4 text-[22px] font-semibold">We couldn't check this payment</h1>
            <p className="mt-2 text-[14px] text-ink-2">{error}</p>
            <div className="mt-6"><ButtonLink to="/app/wallet" variant="secondary">Go to wallet</ButtonLink></div>
          </>
        ) : !payment ? (
          <div className="flex items-center justify-center gap-3 py-6 text-ink-2"><Spinner /> Confirming with Paystack…</div>
        ) : payment.status === "success" ? (
          <>
            <CheckCircle2 size={44} className="mx-auto text-good" />
            <h1 className="mt-4 text-[24px] font-semibold">Payment received</h1>
            <p className="mt-2 text-[14px] leading-6 text-ink-2">
              {naira(payment.net_kobo ?? payment.expected_net_kobo)} was added to your wallet
              {payment.fees_kobo ? ` (Paystack fee ${naira(payment.fees_kobo)})` : ""}.
              {payment.purpose === "payroll" && payment.payroll_run?.status === "ready" && " Your payroll is funded — the last step is to disburse it."}
              {payment.purpose === "invoice" && " Your subscription is updated."}
            </p>
            <div className="mt-6"><ButtonLink to={next.to} size="lg">{next.label}</ButtonLink></div>
          </>
        ) : payment.status === "pending" ? (
          <>
            <Clock size={40} className="mx-auto text-warn" />
            <h1 className="mt-4 text-[22px] font-semibold">Waiting for confirmation</h1>
            <p className="mt-2 text-[14px] leading-6 text-ink-2">
              Paystack hasn't confirmed this payment yet. Bank transfers can take a few minutes — we'll update your wallet automatically and email you.
            </p>
            <div className="mt-6 flex justify-center gap-2">
              <ButtonLink to={next.to} variant="secondary">{next.label}</ButtonLink>
            </div>
          </>
        ) : (
          <>
            <XCircle size={40} className="mx-auto text-bad" />
            <h1 className="mt-4 text-[22px] font-semibold">Payment not completed</h1>
            <p className="mt-2 text-[14px] text-ink-2">No money was taken. You can try again.</p>
            <div className="mt-6"><ButtonLink to={next.to} variant="secondary">{next.label}</ButtonLink></div>
          </>
        )}
        {reference && <p className="num mt-6 text-[12px] text-ink-3">Reference {reference}</p>}
      </Card>
      <p className="mt-4 text-center text-[12.5px] text-ink-3"><Link to="/app" className="hover:underline">Back to overview</Link></p>
    </div>
  );
}
