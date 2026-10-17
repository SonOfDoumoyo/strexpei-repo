import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Check, CheckCircle2, CreditCard, Download, Printer, RotateCcw, Send, Trash2, XCircle } from "lucide-react";
import { PasswordModal } from "../../components/PasswordModal";
import { Receipt } from "../../components/Receipt";
import { Badge, Button, Card, CardHeader, CopyButton, cx, ErrorState, IconButton, Modal, Notice, PageLoader, Progress, Segmented, Spinner, StatusPill, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup, useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { dateTime, naira, plural } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Dva, Payment, PayrollRun } from "../../lib/types";

const STEPS = ["Review", "Fund", "Disburse", "Paid"];

function stepFor(status: PayrollRun["status"]): number {
  return { draft: 0, awaiting_funding: 1, ready: 2, processing: 3, completed: 4, partially_failed: 4, failed: 4, canceled: -1 }[status];
}

function RunStepper({ run }: { run: PayrollRun }) {
  const current = stepFor(run.status);
  if (current < 0) return null;
  return (
    <ol className="mb-6 grid grid-cols-4 gap-2" aria-label="Payroll progress">
      {STEPS.map((label, i) => {
        const done = i < current || (i === 3 && current === 4);
        const active = i === current || (i === 3 && current === 3);
        return (
          <li key={label} className="grid gap-2">
            <div className={cx("h-1.5 rounded-full", done ? "bg-good" : active ? "bg-brand" : "bg-ink/10")} />
            <span className={cx("flex items-center gap-1.5 text-[12.5px] font-medium", done ? "text-good" : active ? "text-ink" : "text-ink-3")}>
              {done && <Check size={13} strokeWidth={3} />}
              {i === 3 && run.status === "processing" ? "Paying" : label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function FundingPanel({ run, onChanged }: { run: PayrollRun; onChanged: () => void }) {
  const workgroup = useWorkgroup();
  const { refresh } = useWorkgroups();
  const toast = useToast();
  const funding = run.funding!;
  const [tab, setTab] = useState<"transfer" | "card">("transfer");
  const [dva, setDva] = useState<Dva | null>(workgroup.dva);

  const start = useMutation({
    mutationFn: (channel: "checkout" | "transfer") => api.post<Payment>(`/workgroups/${workgroup.id}/payroll/runs/${run.id}/fund`, { channel }),
    onSuccess: (payment) => {
      if (payment.authorization_url) window.location.href = payment.authorization_url;
    },
    onError: (e) => toast.error(e),
  });
  const createDva = useMutation({
    mutationFn: () => api.post<Dva>(`/workgroups/${workgroup.id}/wallet/dva`),
    onSuccess: async (d) => {
      setDva(d);
      await refresh();
      onChanged();
    },
  });
  const verify = useMutation({
    mutationFn: (reference: string) => api.post<Payment>(`/payments/${reference}/verify`),
    onSuccess: (p) => {
      if (p.status === "success") {
        toast.success("Payment received");
        onChanged();
      } else toast.info("Not received yet", "Paystack hasn't confirmed this payment. We'll keep checking.");
    },
    onError: (e) => toast.error(e),
  });

  const transferQuote = run.funding?.transfer;
  const gross = transferQuote?.gross_kobo ?? funding.checkout?.gross_kobo ?? funding.request_kobo;

  return (
    <div className="grid gap-4">
      <div>
        <p className="text-[13px] text-ink-3">Add to the wallet to cover this payroll</p>
        <p className="font-display text-[26px] font-semibold">{naira(funding.shortfall_kobo)}</p>
      </div>
      {run.pending_payment && (
        <Notice tone="info" title="Waiting for your payment" action={<Button size="sm" variant="secondary" loading={verify.isPending} onClick={() => verify.mutate(run.pending_payment!.reference)}>Check now</Button>}>
          Started {dateTime(run.pending_payment.created_at)}. This page updates when Paystack confirms it.
        </Notice>
      )}
      <Segmented
        value={tab}
        onChange={setTab}
        options={[
          { value: "transfer", label: <span className="inline-flex items-center gap-1.5"><Building2 size={14} /> Bank transfer</span> },
          { value: "card", label: <span className="inline-flex items-center gap-1.5"><CreditCard size={14} /> Card & others</span> },
        ]}
      />
      {tab === "transfer" ? (
        dva ? (
          <div className="grid gap-3 rounded-2xl border border-line bg-raised p-4">
            <p className="text-[13px] text-ink-2">Transfer this exact amount from your business account:</p>
            <div className="flex items-center justify-between gap-3">
              <span className="font-display text-[24px] font-semibold">{naira(transferQuote?.gross_kobo ?? gross)}</span>
              <CopyButton text={String((transferQuote?.gross_kobo ?? gross) / 100)} label="Copy amount" />
            </div>
            <div className="grid gap-1 border-t border-line pt-3 text-[13.5px]">
              <div className="flex items-center justify-between gap-2">
                <span className="text-ink-3">Account number</span>
                <span className="flex items-center gap-2">
                  <span className="num text-[16px] font-semibold tracking-wide">{dva.account_number}</span>
                  <CopyButton text={dva.account_number} label="Copy" variant="ghost" />
                </span>
              </div>
              <div className="flex justify-between gap-2"><span className="text-ink-3">Bank</span><span className="font-medium">{dva.bank_name}</span></div>
              <div className="flex justify-between gap-2"><span className="text-ink-3">Account name</span><span className="text-right font-medium">{dva.account_name}</span></div>
            </div>
            <p className="flex items-center gap-2 text-[12.5px] text-ink-3">
              <Spinner size={13} /> Includes Paystack's {naira(transferQuote?.fee_kobo ?? 0)} transfer fee. We'll detect it automatically.
            </p>
          </div>
        ) : (
          <div className="grid gap-3">
            <p className="text-[13px] leading-6 text-ink-2">Get a bank account number for this workgroup. Any transfer to it lands in your wallet within minutes — reuse it every month.</p>
            {createDva.error && <Notice tone="warn">{(createDva.error as ApiError).message}</Notice>}
            <div className="flex flex-wrap gap-2">
              <Button variant="dark" loading={createDva.isPending} onClick={() => createDva.mutate()}>
                Get an account number
              </Button>
              <Button variant="secondary" loading={start.isPending && start.variables === "transfer"} onClick={() => start.mutate("transfer")}>
                One-time transfer via Paystack
              </Button>
            </div>
          </div>
        )
      ) : (
        <div className="grid gap-3 rounded-2xl border border-line bg-raised p-4">
          <div className="flex items-baseline justify-between text-[13.5px]">
            <span className="text-ink-2">You pay</span>
            <span className="num font-semibold">{naira(funding.checkout?.gross_kobo)}</span>
          </div>
          <div className="flex items-baseline justify-between text-[13px] text-ink-3">
            <span>Paystack fee</span>
            <span className="num">{naira(funding.checkout?.fee_kobo)}</span>
          </div>
          <div className="flex items-baseline justify-between text-[13px] text-ink-3">
            <span>Added to wallet</span>
            <span className="num">{naira(funding.checkout?.net_kobo)}</span>
          </div>
          <Button size="lg" loading={start.isPending && start.variables === "checkout"} onClick={() => start.mutate("checkout")}>
            Pay {naira(funding.checkout?.gross_kobo)} with Paystack
          </Button>
          <p className="text-[12px] text-ink-3">Card, bank, USSD or transfer on Paystack's secure page. You'll come straight back here.</p>
        </div>
      )}
    </div>
  );
}

export default function PayrollRunPage() {
  const { runId = "" } = useParams();
  const workgroup = useWorkgroup();
  const { refresh } = useWorkgroups();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [disburseOpen, setDisburseOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const key = wgKey(workgroup.id, "run", runId);
  const q = useQuery({
    queryKey: key,
    queryFn: () => api.get<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${runId}`),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" ? 3000 : status === "awaiting_funding" ? 6000 : false;
    },
  });
  const update = (run: PayrollRun) => {
    qc.setQueryData(key, run);
    qc.invalidateQueries({ queryKey: ["wg", workgroup.id], predicate: (x) => x.queryKey[2] !== "run" });
    void refresh();
  };
  const submit = useMutation({
    mutationFn: () => api.post<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${runId}/submit`),
    onSuccess: update,
    onError: (e) => toast.error(e),
  });
  const removeItem = useMutation({
    mutationFn: (itemId: string) => api.delete<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${runId}/items/${itemId}`),
    onSuccess: update,
    onError: (e) => toast.error(e),
  });
  const cancel = useMutation({
    mutationFn: () => api.post<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${runId}/cancel`),
    onSuccess: (r) => {
      update(r);
      setCancelOpen(false);
      toast.success("Payroll cancelled");
    },
    onError: (e) => toast.error(e),
  });
  const retry = useMutation({
    mutationFn: () => api.post<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${runId}/retry`),
    onSuccess: (r) => {
      toast.success("New payroll prepared", "It contains only the staff whose payment failed.");
      navigate(`/app/payroll/runs/${r.id}`);
    },
    onError: (e) => toast.error(e),
  });

  if (q.isLoading) return <PageLoader />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const run = q.data;
  const items = run.items ?? [];
  const editable = ["draft", "awaiting_funding", "ready"].includes(run.status);
  const progress = run.progress!;
  const finished = ["completed", "partially_failed", "failed"].includes(run.status);
  const balance = run.wallet_balance_kobo ?? workgroup.wallet_balance_kobo;

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 md:flex-row md:items-end md:justify-between">
        <div>
          <Link to="/app/payroll" className="mb-3 inline-flex text-[13px] font-medium text-ink-3 hover:text-ink">← Payroll</Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[28px] font-semibold leading-tight sm:text-[34px]">{run.period_label} payroll</h1>
            <StatusPill status={run.status} />
          </div>
          <p className="num mt-1.5 text-[13px] text-ink-3">
            {run.number} · {plural(run.staff_count, "staff member")}
            {run.trigger === "automatic" && " · prepared automatically on payday"}
            {run.note && ` · ${run.note}`}
          </p>
        </div>
        <div className="no-print flex flex-wrap gap-2">
          <Button variant="secondary" icon={<Download size={15} />} onClick={() => api.download(`/workgroups/${workgroup.id}/payroll/runs/${run.id}/export`, `${run.number}.csv`).catch(toast.error)}>
            CSV
          </Button>
          <Button variant="secondary" icon={<Printer size={15} />} onClick={() => window.print()}>
            Print
          </Button>
          {editable && (
            <Button variant="ghost" onClick={() => setCancelOpen(true)}>
              Cancel payroll
            </Button>
          )}
        </div>
      </div>

      <div className="no-print">
        <RunStepper run={run} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_400px]">
        <Card className="overflow-hidden lg:order-1 lg:self-start">
          <CardHeader
            title="Staff payments"
            description={editable ? "Remove anyone who shouldn't be paid in this run." : finished ? `${progress.success} paid${progress.failed ? `, ${progress.failed} failed` : ""}` : undefined}
          />
          <Table>
            <thead>
              <tr>
                <Th>Staff</Th>
                <Th>Bank</Th>
                <Th align="right">Amount</Th>
                <Th>Status</Th>
                {editable && <Th className="no-print" />}
              </tr>
            </thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <Td>
                    <p className="font-medium">{i.staff_name}</p>
                    <p className="num text-[12px] text-ink-3">
                      {i.staff_code}
                      {i.role_name ? ` · ${i.role_name}` : ""}
                    </p>
                  </Td>
                  <Td className="text-ink-2">
                    {i.bank_name} <span className="num">{i.account_number_masked}</span>
                    {i.account_name && <p className="text-[12px] text-ink-3">{i.account_name}</p>}
                  </Td>
                  <Td align="right" className="font-medium">{naira(i.amount_kobo)}</Td>
                  <Td>
                    {editable ? (
                      <Badge tone="neutral" dot={false}>Included</Badge>
                    ) : (
                      <div>
                        <StatusPill status={i.status} />
                        {i.failure_reason && <p className="mt-1 max-w-[220px] text-[12px] leading-4 text-bad">{i.failure_reason}{i.refunded ? " — refunded" : ""}</p>}
                      </div>
                    )}
                  </Td>
                  {editable && (
                    <Td align="right" className="no-print">
                      <IconButton label={`Remove ${i.staff_name}`} disabled={removeItem.isPending} onClick={() => removeItem.mutate(i.id)}>
                        <Trash2 size={15} />
                      </IconButton>
                    </Td>
                  )}
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>

        <div className="grid content-start gap-4 lg:order-2">
          <Receipt
            title="Payroll cost"
            lines={[
              { label: `Salaries · ${plural(run.staff_count, "staff member")}`, value: run.salaries_kobo },
              { label: "Paystack transfer fees", value: run.transfer_fees_kobo, muted: true },
              { label: `Streixpei service fee (${run.commission_label})`, value: run.commission_kobo, muted: true },
            ]}
            total={{ label: "Total", value: run.total_kobo }}
            footer={
              <div className="no-print grid gap-4">
                {run.status === "draft" && (
                  <>
                    <p className="text-[13px] leading-6 text-ink-2">Check the list, then continue. We'll use your wallet balance of {naira(balance)} first.</p>
                    <Button size="lg" loading={submit.isPending} onClick={() => submit.mutate()}>
                      Continue
                    </Button>
                  </>
                )}
                {run.status === "awaiting_funding" && run.funding && <FundingPanel run={run} onChanged={() => q.refetch()} />}
                {run.status === "ready" && (
                  <>
                    <div className="flex items-center gap-2 text-[13.5px] font-medium text-good">
                      <CheckCircle2 size={17} /> Funds confirmed — wallet has {naira(balance)}
                    </div>
                    <Button size="lg" icon={<Send size={16} />} onClick={() => setDisburseOpen(true)}>
                      Pay {plural(run.staff_count, "staff member")} {naira(run.salaries_kobo)}
                    </Button>
                    <p className="text-[12px] leading-5 text-ink-3">Transfers go out immediately through Paystack. Each staff member gets an email receipt.</p>
                  </>
                )}
                {run.status === "processing" && (
                  <div className="grid gap-3">
                    <div className="flex items-center gap-2 text-[13.5px] font-semibold">
                      <Spinner size={15} /> Sending to banks…
                    </div>
                    <Progress value={progress.success + progress.failed} max={progress.total} label="Transfers settled" />
                    <p className="num text-[12.5px] text-ink-3">
                      {progress.success} paid · {progress.processing} in progress{progress.failed ? ` · ${progress.failed} failed` : ""}
                    </p>
                  </div>
                )}
                {finished && (
                  <div className="grid gap-3">
                    <div className={cx("flex items-center gap-2 text-[14px] font-semibold", run.status === "completed" ? "text-good" : "text-warn")}>
                      {run.status === "completed" ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
                      {run.status === "completed" ? `All ${progress.success} staff paid` : `${progress.success} paid, ${progress.failed} failed`}
                    </div>
                    <div className="grid gap-1.5 text-[13px]">
                      <div className="flex justify-between"><span className="text-ink-3">Paid to staff</span><span className="num font-medium">{naira(run.paid_kobo)}</span></div>
                      {run.refunded_kobo > 0 && <div className="flex justify-between"><span className="text-ink-3">Refunded to wallet</span><span className="num font-medium">{naira(run.refunded_kobo)}</span></div>}
                      <div className="flex justify-between"><span className="text-ink-3">Completed</span><span>{dateTime(run.completed_at)}</span></div>
                    </div>
                    {progress.failed > 0 && (
                      <Button variant="dark" icon={<RotateCcw size={15} />} loading={retry.isPending} onClick={() => retry.mutate()}>
                        Retry failed payments
                      </Button>
                    )}
                  </div>
                )}
                {run.status === "canceled" && <p className="text-[13px] text-ink-3">This payroll was cancelled {dateTime(run.canceled_at)}. Nothing was paid.</p>}
              </div>
            }
          />
          {run.disbursed_at && <p className="px-1 text-[12px] text-ink-3">Disbursed {dateTime(run.disbursed_at)}</p>}
        </div>
      </div>

      <PasswordModal
        open={disburseOpen}
        onClose={() => setDisburseOpen(false)}
        title="Confirm payment"
        description={`${naira(run.salaries_kobo)} will be sent to ${plural(run.staff_count, "staff member")}, and ${naira(run.total_kobo)} taken from the wallet including fees. This can't be undone.`}
        confirmLabel={`Pay ${naira(run.salaries_kobo)}`}
        onConfirm={async (password) => {
          const result = await api.post<PayrollRun>(`/workgroups/${workgroup.id}/payroll/runs/${run.id}/disburse`, { password });
          update(result);
          setDisburseOpen(false);
          const failed = result.items?.filter((i) => i.status === "failed").length ?? 0;
          if (result.status === "completed") toast.success("Everyone has been paid", "Staff receive email receipts as each transfer lands.");
          else if (result.status === "partially_failed" || result.status === "failed")
            toast.error(
              result.status === "failed" ? "No payments went through" : `Payroll finished — ${failed === 1 ? "1 payment" : `${failed} payments`} failed`,
              "Failed amounts, fees included, are back in your wallet. Check the bank details and retry.",
            );
          else toast.success("Payroll is on its way", "Staff receive email receipts as each transfer lands.");
        }}
      />
      <Modal
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        size="sm"
        title="Cancel this payroll?"
        description="Nothing has been paid. Any money you've added stays in the wallet for next time."
        footer={
          <>
            <Button variant="ghost" onClick={() => setCancelOpen(false)}>Keep it</Button>
            <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate()}>Cancel payroll</Button>
          </>
        }
      />
    </div>
  );
}
