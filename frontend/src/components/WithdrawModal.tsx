import { type FormEvent, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { BankPicker } from "./BankPicker";
import { Button, Input, Modal, MoneyInput, Notice, Spinner } from "./ui";
import { ApiError, api } from "../lib/api";
import { naira } from "../lib/format";
import { useBanks } from "../lib/queries";
import type { Withdrawal, WithdrawalQuote } from "../lib/types";

type Resolved = { account_name: string; bank_name: string };

function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/**
 * Two steps in one dialog: choose amount and account (the account is checked
 * with the bank as soon as it's complete), then confirm with the password.
 */
export function WithdrawModal({
  open,
  onClose,
  workgroupId,
  balanceKobo,
  nextPayrollKobo,
  last,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  workgroupId: string;
  balanceKobo: number;
  nextPayrollKobo: number;
  last?: Withdrawal | null;
  onDone: (w: Withdrawal) => void;
}) {
  const banks = useBanks();
  const [step, setStep] = useState<"details" | "confirm">("details");
  const [amount, setAmount] = useState<number | null>(null);
  const [bank, setBank] = useState("");
  const [account, setAccount] = useState("");
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [resolving, setResolving] = useState(false);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastKey = useRef("");
  const lastUsed = useRef(last);
  lastUsed.current = last;

  // Start fresh each time it opens, with the last account used filled in.
  useEffect(() => {
    if (!open) return;
    setStep("details");
    setAmount(null);
    setBank(lastUsed.current?.bank_code ?? "");
    setAccount(lastUsed.current?.account_number ?? "");
    setResolved(null);
    setResolveError(null);
    setPassword("");
    setError(null);
    lastKey.current = "";
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const key = `${bank}:${account}`;
    if (!bank || account.length !== 10) {
      setResolved(null);
      lastKey.current = "";
      return;
    }
    if (key === lastKey.current) return;
    lastKey.current = key;
    setResolving(true);
    setResolved(null);
    setResolveError(null);
    api
      .post<Resolved>(`/workgroups/${workgroupId}/wallet/withdrawals/resolve`, { bank_code: bank, account_number: account })
      .then((r) => lastKey.current === key && setResolved(r))
      .catch((e: ApiError) => {
        if (lastKey.current !== key) return;
        setResolveError(e.message);
        lastKey.current = "";
      })
      .finally(() => setResolving(false));
  }, [open, bank, account, workgroupId]);

  const debounced = useDebounced(amount);
  const quote = useQuery({
    queryKey: ["withdraw-quote", workgroupId, debounced ?? 0, balanceKobo],
    queryFn: () => api.get<WithdrawalQuote>(`/workgroups/${workgroupId}/wallet/withdrawals/quote`, { amount_kobo: debounced ?? 0 }),
    enabled: open,
  });
  const q = quote.data;
  const min = q?.min_amount_kobo ?? 100_000;
  const max = q?.max_amount_kobo ?? 0;
  const amountError =
    amount === null ? null : amount < min ? `The smallest withdrawal is ${naira(min)}.` : amount > max ? `You can withdraw up to ${naira(max)} after the transfer fee.` : null;
  const quoteFresh = q && amount !== null && q.amount_kobo === amount;
  const leaves = quoteFresh ? balanceKobo - q.total_kobo : null;
  const canContinue = Boolean(amount && !amountError && resolved && quoteFresh && q.enough);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!password || busy || !amount) return;
    setBusy(true);
    setError(null);
    try {
      const w = await api.post<Withdrawal>(`/workgroups/${workgroupId}/wallet/withdrawals`, {
        amount_kobo: amount,
        bank_code: bank,
        account_number: account,
        password,
      });
      onDone(w);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  const close = () => !busy && onClose();

  if (step === "confirm" && q && amount && resolved) {
    return (
      <Modal
        open={open}
        onClose={close}
        size="sm"
        title={`Withdraw ${naira(amount)}?`}
        description="The money leaves the wallet straight away and usually lands within minutes."
        footer={
          <>
            <Button variant="ghost" disabled={busy} onClick={() => { setStep("details"); setError(null); }}>
              Back
            </Button>
            <Button loading={busy} disabled={!password} onClick={() => submit()}>
              Withdraw {naira(amount)}
            </Button>
          </>
        }
      >
        <form className="grid gap-4" onSubmit={submit}>
          <dl className="grid gap-2 rounded-2xl border border-line bg-raised p-4 text-[13.5px]">
            <div className="flex justify-between gap-3"><dt className="text-ink-3">To</dt><dd className="text-right font-semibold">{resolved.account_name}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-ink-3">Bank</dt><dd className="text-right">{resolved.bank_name} · <span className="num">{account}</span></dd></div>
            <div className="flex justify-between gap-3 border-t border-line pt-2"><dt className="text-ink-3">Amount</dt><dd className="num">{naira(amount)}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-ink-3">Paystack transfer fee</dt><dd className="num">{naira(q.fee_kobo)}</dd></div>
            <div className="flex justify-between gap-3 font-semibold"><dt>Taken from wallet</dt><dd className="num">{naira(q.total_kobo)}</dd></div>
          </dl>
          {error && <Notice tone="bad">{error}</Notice>}
          <Input label="Your password" type="password" autoComplete="current-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} hint="Withdrawals always need your password." />
        </form>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={close}
      title="Withdraw from wallet"
      description={`Send money from the wallet to a Nigerian bank account. Available: ${naira(balanceKobo)}.`}
      footer={
        <>
          <Button variant="ghost" onClick={close}>Cancel</Button>
          <Button disabled={!canContinue} onClick={() => setStep("confirm")}>Continue</Button>
        </>
      }
    >
      <div className="grid gap-5">
        <div className="grid gap-2">
          <MoneyInput label="Amount" valueKobo={amount} onChangeKobo={setAmount} error={amountError} autoFocus />
          {max >= min && (
            <button type="button" onClick={() => setAmount(max)} className="justify-self-start text-[12.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
              Withdraw everything ({naira(max)})
            </button>
          )}
        </div>
        <BankPicker banks={banks.data ?? []} loading={banks.isLoading} value={bank} onChange={setBank} />
        <Input
          label="Account number"
          inputMode="numeric"
          autoComplete="off"
          maxLength={10}
          placeholder="10 digits"
          className="num font-semibold tracking-wider"
          value={account}
          onChange={(e) => setAccount(e.target.value.replace(/\D/g, "").slice(0, 10))}
          error={resolveError}
        />
        {resolving && <p className="flex items-center gap-2 text-[13px] text-ink-2"><Spinner size={14} /> Checking with the bank…</p>}
        {resolved && (
          <div className="rounded-2xl border border-good/30 bg-good-soft p-4">
            <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-good"><ShieldCheck size={14} /> Account found</p>
            <p className="mt-1 text-[16px] font-semibold">{resolved.account_name}</p>
            <p className="text-[13px] text-ink-2">{resolved.bank_name} · <span className="num">{account}</span></p>
          </div>
        )}
        {quoteFresh && !amountError && (
          <div className="grid gap-1.5 rounded-xl bg-soft/60 px-4 py-3 text-[13px]">
            <div className="flex justify-between text-ink-3"><span>Paystack transfer fee</span><span className="num">{naira(q.fee_kobo)}</span></div>
            <div className="flex justify-between font-semibold"><span>Taken from wallet</span><span className="num">{naira(q.total_kobo)}</span></div>
            <div className="flex justify-between text-ink-3"><span>Left in wallet</span><span className="num">{naira(leaves ?? 0)}</span></div>
          </div>
        )}
        {leaves !== null && !amountError && nextPayrollKobo > 0 && leaves < nextPayrollKobo && (
          <Notice tone="warn">
            Your next payroll needs about {naira(nextPayrollKobo)}. After this withdrawal you'll need to add {naira(nextPayrollKobo - leaves)} before payday.
          </Notice>
        )}
      </div>
    </Modal>
  );
}
