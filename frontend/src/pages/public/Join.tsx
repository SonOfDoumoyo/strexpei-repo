import { type FormEvent, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";
import { BankPicker } from "../../components/BankPicker";
import { Logo } from "../../components/Logo";
import { Button, cx, Input, Notice, Spinner } from "../../components/ui";
import { ApiError, publicApi } from "../../lib/api";
import { useBanks } from "../../lib/queries";

type JoinInfo = { workgroup: { name: string; address: string | null; industry: string | null }; manager_name: string | null; accepting: boolean; message: string | null; staff_id_hint: string };
type CheckResult = { staff_code: string; preset: { first_name: string | null; last_name: string | null; email: string | null; phone: string | null; role: string | null } };
type Done = { staff_code: string; name: string; workgroup: string; bank_name: string; account_masked: string; account_name: string };

const STEPS = ["Staff ID", "Your details", "Bank account"];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function Join() {
  const { code = "" } = useParams();
  const info = useQuery({ queryKey: ["join", code], queryFn: () => publicApi.get<JoinInfo>(`/join/${code}`), retry: false });
  const banks = useBanks();
  const [step, setStep] = useState(0);
  const [staffCode, setStaffCode] = useState("");
  const [details, setDetails] = useState({ first_name: "", last_name: "", email: "", phone: "" });
  const [bank, setBank] = useState("");
  const [account, setAccount] = useState("");
  const [resolved, setResolved] = useState<{ account_name: string; bank_name: string } | null>(null);
  const [resolving, setResolving] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Done | null>(null);
  const lastResolve = useRef("");

  useEffect(() => {
    document.title = info.data ? `${info.data.workgroup.name} payroll registration` : "Payroll registration";
  }, [info.data]);

  // Look the account name up as soon as bank + 10 digits are in.
  useEffect(() => {
    const key = `${bank}:${account}`;
    if (!bank || account.length !== 10 || key === lastResolve.current) {
      if (account.length !== 10) setResolved(null);
      return;
    }
    lastResolve.current = key;
    setResolving(true);
    setResolved(null);
    setError(null);
    publicApi
      .post<{ account_name: string; bank_name: string }>(`/join/${code}/resolve-account`, { staff_code: staffCode, bank_code: bank, account_number: account })
      .then(setResolved)
      .catch((e: ApiError) => {
        setError(e.message);
        lastResolve.current = "";
      })
      .finally(() => setResolving(false));
  }, [bank, account, code, staffCode]);

  async function checkId(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await publicApi.post<CheckResult>(`/join/${code}/verify-id`, { staff_code: staffCode.trim() });
      setStaffCode(r.staff_code);
      setDetails((d) => ({
        first_name: d.first_name || r.preset.first_name || "",
        last_name: d.last_name || r.preset.last_name || "",
        email: d.email || r.preset.email || "",
        phone: d.phone || r.preset.phone || "",
      }));
      setStep(1);
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const r = await publicApi.post<Done>(`/join/${code}/register`, { staff_code: staffCode, ...details, phone: details.phone || null, bank_code: bank, account_number: account });
      setDone(r);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr.details?.fields ? Object.values(apiErr.details.fields).join(" ") : apiErr.message);
    } finally {
      setBusy(false);
    }
  }

  const detailsValid = details.first_name.trim() && details.last_name.trim() && EMAIL_RE.test(details.email.trim());

  return (
    <div className="min-h-screen bg-shell">
      <header className="mx-auto flex max-w-xl items-center justify-between px-5 py-5">
        <Logo to={null} compact />
        <span className="inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-3">
          <LockKeyhole size={13} /> Secure registration
        </span>
      </header>
      <main className="mx-auto max-w-xl px-4 pb-16">
        {info.isLoading ? (
          <div className="card grid place-items-center p-12"><Spinner /></div>
        ) : info.error ? (
          <div className="card p-8 text-center">
            <h1 className="text-[24px] font-semibold">This link isn't working</h1>
            <p className="mt-2 text-[14px] leading-6 text-ink-2">{(info.error as ApiError).message}</p>
          </div>
        ) : info.data && !info.data.accepting && !done ? (
          <div className="card p-8 text-center">
            <h1 className="text-[24px] font-semibold">{info.data.workgroup.name}</h1>
            <p className="mt-3 text-[14px] leading-6 text-ink-2">{info.data.message}</p>
          </div>
        ) : done ? (
          <div className="card overflow-hidden">
            <div className="bg-[#100E0B] px-7 pb-8 pt-9 text-[#F6F1E8]">
              <CheckCircle2 size={36} className="text-[#5fbf8a]" />
              <h1 className="mt-5 font-display text-[30px] font-semibold leading-tight">You're on {done.workgroup} payroll.</h1>
              <p className="mt-2 text-[14px] leading-6 text-[#F6F1E8]/65">Thanks, {done.name.split(" ")[0]}. Your salary will be paid to the account below. We've emailed you a confirmation.</p>
            </div>
            <dl className="divide-y divide-line px-7 py-2 text-[14px]">
              {[
                ["Staff ID", done.staff_code],
                ["Account name", done.account_name],
                ["Bank", done.bank_name],
                ["Account", done.account_masked],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 py-3.5">
                  <dt className="text-ink-3">{k}</dt>
                  <dd className="num text-right font-semibold">{v}</dd>
                </div>
              ))}
            </dl>
            <p className="border-t border-line bg-soft/50 px-7 py-4 text-[12.5px] leading-5 text-ink-3">
              Need to change your bank account later? Contact your finance team at {done.workgroup}. You don't need to do anything else.
            </p>
          </div>
        ) : info.data ? (
          <div className="card overflow-hidden">
            <div className="border-b border-line px-6 pb-6 pt-7 sm:px-8">
              <p className="text-[13px] font-medium text-ink-3">Payroll registration</p>
              <h1 className="mt-1 font-display text-[28px] font-semibold leading-tight">{info.data.workgroup.name}</h1>
              {info.data.manager_name && <p className="mt-1 text-[13.5px] text-ink-2">Requested by {info.data.manager_name}</p>}
              <ol className="mt-6 grid grid-cols-3 gap-2" aria-label="Progress">
                {STEPS.map((s, i) => (
                  <li key={s} className="grid gap-1.5">
                    <span className={cx("h-1.5 rounded-full", i < step ? "bg-good" : i === step ? "bg-brand" : "bg-ink/10")} />
                    <span className={cx("text-[12px] font-medium", i === step ? "text-ink" : "text-ink-3")}>{s}</span>
                  </li>
                ))}
              </ol>
            </div>

            <div className="px-6 py-7 sm:px-8">
              {error && <Notice tone="bad" className="mb-5">{error}</Notice>}

              {step === 0 && (
                <form onSubmit={checkId} className="grid gap-5">
                  <Input
                    label="Your staff ID"
                    autoFocus
                    autoCapitalize="characters"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder={info.data.staff_id_hint}
                    className="num text-[17px] font-semibold tracking-wider"
                    value={staffCode}
                    onChange={(e) => setStaffCode(e.target.value.toUpperCase())}
                    hint="Your finance team gave you this ID. It can only be used once."
                  />
                  <Button type="submit" size="lg" loading={busy} disabled={!staffCode.trim()} block>
                    Continue
                  </Button>
                </form>
              )}

              {step === 1 && (
                <form
                  className="grid gap-5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    setError(null);
                    setStep(2);
                  }}
                >
                  <p className="num inline-flex w-fit items-center gap-2 rounded-lg bg-good-soft px-2.5 py-1 text-[12.5px] font-semibold text-good">
                    <BadgeCheck size={14} /> {staffCode} accepted
                  </p>
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Input label="First name" autoComplete="given-name" autoFocus value={details.first_name} onChange={(e) => setDetails({ ...details, first_name: e.target.value })} />
                    <Input label="Last name" autoComplete="family-name" value={details.last_name} onChange={(e) => setDetails({ ...details, last_name: e.target.value })} />
                  </div>
                  <Input
                    label="Email"
                    type="email"
                    autoComplete="email"
                    inputMode="email"
                    value={details.email}
                    onChange={(e) => setDetails({ ...details, email: e.target.value })}
                    hint="We send your payslip here every payday."
                    error={details.email && !EMAIL_RE.test(details.email.trim()) ? "Check this email address." : null}
                  />
                  <Input label="Phone number" type="tel" autoComplete="tel" optional value={details.phone} onChange={(e) => setDetails({ ...details, phone: e.target.value })} />
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => setStep(0)}>Back</Button>
                    <Button type="submit" size="lg" className="flex-1" disabled={!detailsValid}>
                      Continue
                    </Button>
                  </div>
                </form>
              )}

              {step === 2 && (
                <div className="grid gap-5">
                  <BankPicker banks={banks.data ?? []} loading={banks.isLoading} value={bank} onChange={(c) => { setBank(c); setError(null); }} />
                  <Input
                    label="Account number"
                    inputMode="numeric"
                    autoComplete="off"
                    maxLength={10}
                    placeholder="10 digits"
                    className="num text-[16px] font-semibold tracking-wider"
                    value={account}
                    onChange={(e) => { setAccount(e.target.value.replace(/\D/g, "").slice(0, 10)); setError(null); }}
                    hint="Use an account in your own name."
                  />
                  {resolving && (
                    <p className="flex items-center gap-2 text-[13px] text-ink-2"><Spinner size={14} /> Checking with your bank…</p>
                  )}
                  {resolved && (
                    <div className="rounded-2xl border border-good/30 bg-good-soft p-4">
                      <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-good"><ShieldCheck size={14} /> Account found</p>
                      <p className="mt-1.5 text-[17px] font-semibold">{resolved.account_name}</p>
                      <p className="text-[13px] text-ink-2">{resolved.bank_name} · {account}</p>
                    </div>
                  )}
                  <div className="flex gap-2">
                    <Button variant="ghost" onClick={() => setStep(1)}>Back</Button>
                    <Button size="lg" className="flex-1" loading={busy} disabled={!resolved} onClick={submit}>
                      {resolved ? "Yes, that's me — done" : "Done"}
                    </Button>
                  </div>
                  <p className="text-[12px] leading-5 text-ink-3">
                    By submitting, you agree that {info.data.workgroup.name} can pay your salary to this account through Streixpei. We'll never ask for your card, PIN or password.
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : null}
        <p className="mt-6 text-center text-[12px] text-ink-3">Payroll by Streixpei · a Streixcorp company</p>
      </main>
    </div>
  );
}
