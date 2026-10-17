import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { Button, Card, Notice, Spinner } from "../../components/ui";
import { ApiError, publicApi } from "../../lib/api";
import { naira } from "../../lib/format";
import type { Payment } from "../../lib/types";

/** Stand-in for Paystack's checkout when the API runs with PAYMENTS_PROVIDER=fake. */
export default function DevCheckout() {
  const [params] = useSearchParams();
  const reference = params.get("reference") ?? "";
  const navigate = useNavigate();
  const [payment, setPayment] = useState<(Payment & { workgroup: string }) | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    publicApi.get<Payment & { workgroup: string }>(`/dev/checkout/${reference}`).then(setPayment).catch((e: ApiError) => setError(e.message));
  }, [reference]);

  const back = () => navigate(`/app/payments/callback?reference=${reference}`);

  return (
    <div className="grid min-h-screen place-items-center bg-[#0E1A2B] px-4">
      <Card className="w-full max-w-sm p-7">
        <p className="text-[12px] font-semibold text-[#0BA4DB]">Paystack · test checkout</p>
        {error ? (
          <Notice tone="bad" className="mt-4">{error}</Notice>
        ) : !payment ? (
          <div className="mt-6 flex items-center gap-2 text-ink-2"><Spinner /> Loading…</div>
        ) : (
          <>
            <p className="mt-4 text-[13px] text-ink-3">{payment.workgroup}</p>
            <p className="font-display text-[34px] font-semibold">{naira(payment.amount_kobo)}</p>
            <p className="mt-1 text-[12.5px] text-ink-3">{payment.channel === "transfer" ? "Pay with transfer" : "Card"} · simulated, no money moves</p>
            <div className="mt-6 grid gap-2">
              <Button
                size="lg"
                loading={busy}
                disabled={payment.status !== "pending"}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await publicApi.post(`/dev/checkout/${reference}/complete`);
                    back();
                  } catch (e) {
                    setError((e as ApiError).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {payment.status === "pending" ? `Pay ${naira(payment.amount_kobo)}` : "Already paid"}
              </Button>
              <Button variant="ghost" onClick={back}>Cancel payment</Button>
            </div>
            <p className="mt-5 flex items-center gap-1.5 text-[11.5px] text-ink-3"><ShieldCheck size={13} /> Test mode — set PAYMENTS_PROVIDER=paystack for real payments.</p>
          </>
        )}
      </Card>
    </div>
  );
}
