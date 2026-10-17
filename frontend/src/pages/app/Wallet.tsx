import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDownLeft, ArrowUpRight, Building2, CreditCard, Download, Landmark } from "lucide-react";
import { Button, Card, CardHeader, CopyButton, cx, EmptyState, ErrorState, MoneyInput, Notice, PageHeader, Pagination, Segmented, Skeleton, StatusPill, Table, Td, Th } from "../../components/ui";
import { WithdrawModal } from "../../components/WithdrawModal";
import { useToast } from "../../components/toast";
import { useWorkgroup, useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { dateTime, dayLong, naira, relative } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Dva, FundingQuote, Paged, Payment, WalletEntry, WalletInfo, Withdrawal } from "../../lib/types";

const TYPES: { value: string; label: string }[] = [
  { value: "", label: "All" },
  { value: "funding", label: "Top-ups" },
  { value: "payroll", label: "Payroll" },
  { value: "refund", label: "Refunds" },
  { value: "withdrawal", label: "Withdrawals" },
  { value: "subscription", label: "Subscription" },
];

const TYPE_LABEL: Record<string, string> = {
  funding: "Top-up",
  payroll: "Salaries",
  transfer_fees: "Transfer fees",
  commission: "Service fee",
  refund: "Refund",
  subscription: "Subscription",
  withdrawal: "Withdrawal",
  adjustment: "Adjustment",
};

const WITHDRAWAL_LABEL: Record<string, string> = { queued: "Sending", processing: "Sending", success: "Sent" };

function useDebounced<T>(value: T, ms = 350) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function AccountDetails({ dva, amount }: { dva: Dva; amount?: number }) {
  return (
    <div className="grid gap-2 rounded-2xl border border-line bg-raised p-4 text-[13.5px]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-ink-3">Account number</span>
        <span className="flex items-center gap-1">
          <span className="num text-[17px] font-semibold tracking-wide">{dva.account_number}</span>
          <CopyButton text={dva.account_number} label="Copy" variant="ghost" />
        </span>
      </div>
      <div className="flex justify-between gap-2"><span className="text-ink-3">Bank</span><span className="font-medium">{dva.bank_name}</span></div>
      <div className="flex justify-between gap-2"><span className="text-ink-3">Name</span><span className="text-right font-medium">{dva.account_name}</span></div>
      {amount !== undefined && amount > 0 && (
        <div className="mt-1 flex items-center justify-between gap-2 border-t border-line pt-3">
          <span className="text-ink-3">Send exactly</span>
          <span className="flex items-center gap-1">
            <span className="num font-semibold">{naira(amount)}</span>
            <CopyButton text={String(amount / 100)} label="Copy" variant="ghost" />
          </span>
        </div>
      )}
    </div>
  );
}

export default function Wallet() {
  const workgroup = useWorkgroup();
  const { refresh } = useWorkgroups();
  const toast = useToast();
  const qc = useQueryClient();
  const [amount, setAmount] = useState<number | null>(null);
  const [method, setMethod] = useState<"transfer" | "card">("transfer");
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);
  const [withdrawOpen, setWithdrawOpen] = useState(false);

  const info = useQuery({ queryKey: wgKey(workgroup.id, "wallet"), queryFn: () => api.get<WalletInfo>(`/workgroups/${workgroup.id}/wallet`), refetchInterval: 20_000 });
  const entries = useQuery({
    queryKey: wgKey(workgroup.id, "wallet-entries", type, page),
    queryFn: () => api.get<Paged<WalletEntry>>(`/workgroups/${workgroup.id}/wallet/entries`, { type: type || undefined, page, page_size: 25 }),
  });
  const withdrawals = useQuery({
    queryKey: wgKey(workgroup.id, "withdrawals"),
    queryFn: () => api.get<Paged<Withdrawal>>(`/workgroups/${workgroup.id}/wallet/withdrawals`, { page_size: 5 }),
    refetchInterval: (q) => (q.state.data?.items.some((w) => w.status === "queued" || w.status === "processing") ? 5_000 : false),
  });
  const debounced = useDebounced(amount);
  const dva = info.data?.dva ?? null;
  const quoteChannel = method === "card" ? "checkout" : dva ? "dva" : "transfer";
  const quote = useQuery({
    queryKey: ["quote-fund", debounced, quoteChannel],
    queryFn: () => api.get<FundingQuote>(`/workgroups/${workgroup.id}/wallet/quote`, { amount_kobo: debounced, channel: quoteChannel }),
    enabled: Boolean(debounced && debounced >= 10000),
  });

  const fund = useMutation({
    mutationFn: (channel: "checkout" | "transfer") => api.post<Payment>(`/workgroups/${workgroup.id}/wallet/fund`, { amount_kobo: amount, channel }),
    onSuccess: (p) => {
      if (p.authorization_url) window.location.href = p.authorization_url;
    },
    onError: (e) => toast.error(e),
  });
  const createDva = useMutation({
    mutationFn: () => api.post<Dva>(`/workgroups/${workgroup.id}/wallet/dva`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: wgKey(workgroup.id, "wallet") });
      void refresh();
      toast.success("Account number ready", "Transfers to it land in this wallet.");
    },
  });

  if (info.error) return <ErrorState error={info.error} onRetry={() => info.refetch()} />;
  const w = info.data;
  const tooSmall = amount !== null && amount < 10000;

  return (
    <div>
      <PageHeader title="Wallet" description={`Money held for ${workgroup.name}'s payroll. Top up by bank transfer or card, and withdraw to a bank account at any time.`} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
        <div className="grid content-start gap-6">
          <Card className="overflow-hidden">
            <div className="p-6 sm:p-7">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="text-[13px] font-medium text-ink-2">Available balance</p>
                  {w ? <p className="mt-2 font-display text-[44px] font-semibold leading-none tracking-tight sm:text-[52px]">{naira(w.balance_kobo)}</p> : <Skeleton className="mt-2 h-12 w-56" />}
                </div>
                {w && (
                  <Button variant="secondary" icon={<Landmark size={15} />} disabled={w.balance_kobo < 1_000_00} onClick={() => setWithdrawOpen(true)}>
                    Withdraw
                  </Button>
                )}
              </div>
              {w && (
                <div className="mt-6 grid gap-3 sm:grid-cols-3">
                  <div className="rounded-2xl bg-soft/60 p-4">
                    <p className="text-[12px] text-ink-3">Next payroll (est.)</p>
                    <p className="num mt-1 text-[15px] font-semibold">{naira(w.estimated_payroll_kobo)}</p>
                  </div>
                  <div className={cx("rounded-2xl p-4", w.shortfall_kobo > 0 ? "bg-warn-soft" : "bg-good-soft")}>
                    <p className="text-[12px] text-ink-3">{w.shortfall_kobo > 0 ? "Short by" : "Covered"}</p>
                    <p className={cx("num mt-1 text-[15px] font-semibold", w.shortfall_kobo > 0 ? "text-warn" : "text-good")}>{w.shortfall_kobo > 0 ? naira(w.shortfall_kobo) : "Yes"}</p>
                  </div>
                  <div className="rounded-2xl bg-soft/60 p-4">
                    <p className="text-[12px] text-ink-3">Payday ({w.payment_mode})</p>
                    <p className="mt-1 text-[15px] font-semibold">{dayLong(w.next_payday_at)}</p>
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <CardHeader
              title="Statement"
              action={
                <Button size="sm" variant="secondary" icon={<Download size={14} />} onClick={() => api.download(`/workgroups/${workgroup.id}/wallet/entries/export`, "wallet-statement.csv").catch(toast.error)}>
                  Export
                </Button>
              }
            />
            <div className="border-b border-line px-4 py-3">
              <Segmented size="sm" value={type} onChange={(v) => { setType(v); setPage(1); }} options={TYPES} />
            </div>
            {entries.isLoading ? (
              <div className="grid gap-2 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11" />)}</div>
            ) : !entries.data?.items.length ? (
              <EmptyState title="No transactions yet">Top-ups, payroll and refunds appear here with a running balance.</EmptyState>
            ) : (
              <>
                <Table minWidth={460}>
                  <thead>
                    <tr>
                      <Th>Transaction</Th>
                      <Th align="right">Amount</Th>
                      <Th align="right">Balance</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {entries.data.items.map((e) => (
                      <tr key={e.id}>
                        <Td>
                          <div className="flex items-center gap-3">
                            <span className={cx("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", e.direction === "credit" ? "bg-good-soft text-good" : "bg-soft text-ink-2")}>
                              {e.direction === "credit" ? <ArrowDownLeft size={15} /> : <ArrowUpRight size={15} />}
                            </span>
                            <div className="min-w-0">
                              <p className="font-medium">{TYPE_LABEL[e.type] ?? e.type}</p>
                              <p className="line-clamp-2 max-w-[340px] text-[12px] leading-[18px] text-ink-3" title={e.description}>{e.description}</p>
                              <p className="mt-0.5 text-[11.5px] text-ink-3">{dateTime(e.created_at)}</p>
                            </div>
                          </div>
                        </Td>
                        <Td align="right" className={cx("whitespace-nowrap font-semibold", e.direction === "credit" && "text-good")}>
                          {e.direction === "credit" ? "+" : "−"}
                          {naira(e.amount_kobo)}
                        </Td>
                        <Td align="right" className="whitespace-nowrap text-ink-2">{naira(e.balance_after_kobo)}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
                <Pagination page={page} pageSize={25} total={entries.data.total} onPage={setPage} />
              </>
            )}
          </Card>
        </div>

        <div className="grid content-start gap-6">
          <Card>
            <CardHeader title="Add money" />
            <div className="grid gap-4 p-5 sm:p-6">
              <MoneyInput label="Amount to add" valueKobo={amount} onChangeKobo={setAmount} error={tooSmall ? "The minimum is ₦100." : null} />
              <div className="flex flex-wrap gap-2">
                {[w?.shortfall_kobo || 0, 100_000_00, 500_000_00, 1_000_000_00].filter((v, i, arr) => v > 0 && arr.indexOf(v) === i).map((v) => (
                  <button key={v} type="button" onClick={() => setAmount(v)} className={cx("num h-8 rounded-lg border px-2.5 text-[12.5px] font-semibold transition", amount === v ? "border-brand bg-brand-soft" : "border-line hover:border-line-strong")}>
                    {v === w?.shortfall_kobo ? `Shortfall ${naira(v)}` : naira(v)}
                  </button>
                ))}
              </div>
              <Segmented
                value={method}
                onChange={setMethod}
                options={[
                  { value: "transfer", label: <span className="inline-flex items-center gap-1.5"><Building2 size={14} /> Bank transfer</span> },
                  { value: "card", label: <span className="inline-flex items-center gap-1.5"><CreditCard size={14} /> Card & others</span> },
                ]}
              />
              {quote.data && amount && amount >= 10000 && (
                <div className="grid gap-1.5 rounded-xl bg-soft/60 px-4 py-3 text-[13px]">
                  <div className="flex justify-between"><span className="text-ink-2">You {method === "card" ? "pay" : "send"}</span><span className="num font-semibold">{naira(quote.data.gross_kobo)}</span></div>
                  <div className="flex justify-between text-ink-3"><span>Paystack fee</span><span className="num">{naira(quote.data.fee_kobo)}</span></div>
                  <div className="flex justify-between text-ink-3"><span>Wallet receives</span><span className="num">{naira(quote.data.net_kobo)}</span></div>
                </div>
              )}
              {method === "transfer" ? (
                dva ? (
                  <>
                    <AccountDetails dva={dva} amount={quote.data && amount && amount >= 10000 ? quote.data.gross_kobo : undefined} />
                    <p className="text-[12px] leading-5 text-ink-3">Transfers usually reflect within minutes. You'll get an email when the money lands.</p>
                  </>
                ) : (
                  <div className="grid gap-2">
                    {createDva.error && <Notice tone="warn">{(createDva.error as ApiError).message}</Notice>}
                    {w?.dva_available && (
                      <Button variant="dark" loading={createDva.isPending} onClick={() => createDva.mutate()}>
                        Get a permanent account number
                      </Button>
                    )}
                    <Button variant="secondary" loading={fund.isPending} disabled={!amount || tooSmall} onClick={() => fund.mutate("transfer")}>
                      One-time transfer via Paystack
                    </Button>
                  </div>
                )
              ) : (
                <Button size="lg" loading={fund.isPending} disabled={!amount || tooSmall} onClick={() => fund.mutate("checkout")}>
                  {quote.data && amount ? `Pay ${naira(quote.data.gross_kobo)}` : "Continue to Paystack"}
                </Button>
              )}
            </div>
          </Card>
          {withdrawals.data?.items.length ? (
            <Card>
              <CardHeader title="Withdrawals" description="Money sent from this wallet to a bank account." />
              <ul className="divide-y divide-line">
                {withdrawals.data.items.map((wd) => (
                  <li key={wd.id} className="flex items-start justify-between gap-3 px-5 py-3.5 text-[13px]">
                    <div className="min-w-0">
                      <p className="num font-semibold">{naira(wd.amount_kobo)}</p>
                      <p className="truncate text-[12px] text-ink-3">
                        {wd.account_name} · {wd.bank_name} {wd.account_number_masked}
                      </p>
                      {wd.failure_reason && (
                        <p className="mt-0.5 text-[12px] text-bad">
                          {wd.failure_reason}
                          {wd.refunded ? " — refunded" : ""}
                        </p>
                      )}
                    </div>
                    <div className="shrink-0 text-right">
                      <StatusPill status={wd.status} label={WITHDRAWAL_LABEL[wd.status]} />
                      <p className="mt-1 text-[11.5px] text-ink-3">{relative(wd.created_at)}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
          {w && (w.totals.commission || w.totals.transfer_fees) ? (
            <Card className="p-5 text-[13px]">
              <p className="font-semibold">Fees charged so far</p>
              <p className="mt-0.5 text-[12px] text-ink-3">Fees on failed transfers are refunded with the salary.</p>
              <div className="mt-3 grid gap-1.5 text-ink-2">
                <div className="flex justify-between"><span>Paystack transfer fees</span><span className="num">{naira(w.totals.transfer_fees ?? 0)}</span></div>
                <div className="flex justify-between"><span>Streixpei service fee</span><span className="num">{naira(w.totals.commission ?? 0)}</span></div>
              </div>
            </Card>
          ) : null}
        </div>
      </div>

      {w && (
        <WithdrawModal
          open={withdrawOpen}
          onClose={() => setWithdrawOpen(false)}
          workgroupId={workgroup.id}
          balanceKobo={w.balance_kobo}
          nextPayrollKobo={w.estimated_payroll_kobo}
          last={withdrawals.data?.items.find((x) => x.status === "success") ?? null}
          onDone={(wd) => {
            setWithdrawOpen(false);
            qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "wg" && q.queryKey[1] === workgroup.id });
            void refresh();
            if (wd.status === "failed" || wd.status === "reversed") {
              toast.error("The withdrawal didn't go through", `${wd.failure_reason ?? "The bank declined it."} ${naira(wd.total_kobo)} is back in your wallet.`);
            } else if (wd.status === "success") {
              toast.success(`${naira(wd.amount_kobo)} sent to ${wd.account_name}`, "You'll get an email confirmation too.");
            } else {
              toast.success("Withdrawal on its way", "We'll email you when the bank confirms it.");
            }
          }}
        />
      )}
    </div>
  );
}
