import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Building2, CalendarClock, Check, FileText, Moon, QrCode, ShieldCheck, Sparkles, Sun } from "lucide-react";
import { Logo } from "../../components/Logo";
import { ButtonLink, cx } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { useTheme } from "../../context/theme";
import { publicApi } from "../../lib/api";
import { naira } from "../../lib/format";
import { useMeta } from "../../lib/queries";
import type { Plan } from "../../lib/types";

function PhoneForm() {
  return (
    <div className="relative w-[228px] shrink-0 rounded-[34px] border border-line-strong bg-raised p-2.5 shadow-[var(--shadow-pop)]">
      <div className="rounded-[26px] bg-shell px-4 pb-5 pt-4">
        <div className="mx-auto mb-4 h-1.5 w-14 rounded-full bg-ink/15" />
        <p className="text-[10.5px] font-medium text-ink-3">Payroll registration</p>
        <p className="font-display text-[17px] font-semibold leading-tight">Acme Logistics</p>
        <div className="mt-4 grid gap-2.5">
          <div>
            <p className="mb-1 text-[10.5px] font-medium text-ink-2">Your staff ID</p>
            <div className="num flex h-9 items-center justify-between rounded-xl border border-good/50 bg-raised px-3 text-[12.5px] font-semibold tracking-wider">
              ACM-7K3M-Q9TD <BadgeCheck size={14} className="text-good" />
            </div>
          </div>
          <div>
            <p className="mb-1 text-[10.5px] font-medium text-ink-2">Bank</p>
            <div className="flex h-9 items-center rounded-xl border border-line bg-raised px-3 text-[12.5px]">Guaranty Trust Bank</div>
          </div>
          <div>
            <p className="mb-1 text-[10.5px] font-medium text-ink-2">Account number</p>
            <div className="num flex h-9 items-center rounded-xl border border-line bg-raised px-3 text-[12.5px] font-semibold tracking-wider">0123456789</div>
          </div>
          <div className="rounded-xl border border-good/30 bg-good-soft px-3 py-2">
            <p className="text-[10px] font-semibold text-good">Account found</p>
            <p className="text-[12.5px] font-semibold">CHIDI EZE</p>
          </div>
          <div className="mt-1 flex h-9 items-center justify-center rounded-xl bg-brand text-[12.5px] font-semibold text-brand-ink">Yes, that's me — done</div>
        </div>
      </div>
    </div>
  );
}

function HeroReceipt() {
  const rows: [string, string][] = [
    ["Salaries · 48 staff", "₦8,420,000"],
    ["Paystack transfer fees", "₦4,800"],
    ["Streixpei service fee (0.5%)", "₦42,100"],
  ];
  return (
    <div className="w-full max-w-[300px] overflow-hidden rounded-[24px] border border-line bg-surface shadow-[var(--shadow-pop)]">
      <div className="px-5 pb-5 pt-5">
        <div className="flex items-center justify-between">
          <p className="text-[12.5px] font-medium text-ink-3">October payroll</p>
          <span className="inline-flex items-center gap-1 rounded-full bg-brand-soft px-2 py-0.5 text-[11px] font-semibold text-brand-strong dark:text-brand">
            <span className="h-1.5 w-1.5 rounded-full bg-current" /> Ready to pay
          </span>
        </div>
        <dl className="mt-4 grid gap-2.5 text-[13px]">
          {rows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3">
              <dt className="text-ink-2">{k}</dt>
              <dd className="num font-medium">{v}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 flex items-baseline justify-between border-t border-dashed border-line-strong pt-4">
          <span className="text-[13.5px] font-semibold">Total</span>
          <span className="font-display text-[24px] font-semibold">₦8,466,900</span>
        </div>
      </div>
      <div className="border-t border-line bg-soft/50 px-5 py-4">
        <div className="flex h-11 items-center justify-center rounded-xl bg-brand text-[13.5px] font-semibold text-brand-ink">Pay 48 staff ₦8,420,000</div>
        <p className="mt-2.5 text-center text-[11.5px] text-ink-3">Every staff member gets an email payslip.</p>
      </div>
    </div>
  );
}

function PricingCalculator({ plans, commission }: { plans: Plan[]; commission: string }) {
  const [staff, setStaff] = useState(40);
  const [salary, setSalary] = useState(150_000);
  const plan = useMemo(() => plans.find((p) => staff >= p.min_staff && (p.max_staff === null || staff <= p.max_staff)) ?? plans[plans.length - 1], [plans, staff]);
  if (!plan) return null;
  const subscription = plan.base_fee_kobo + plan.per_staff_kobo * staff;
  const commissionKobo = Math.round(staff * salary * 100 * (parseFloat(commission) / 100));
  const transferFee = salary > 50_000 ? 50_00 : salary > 5_000 ? 25_00 : 10_00;
  const stamp = salary >= 10_000 ? 50_00 : 0;
  const fees = staff * (transferFee + stamp);
  return (
    <div className="grid gap-8 rounded-[28px] border border-line bg-surface p-6 sm:p-9 lg:grid-cols-[1fr_380px]">
      <div className="grid content-start gap-8">
        <label className="grid gap-3">
          <span className="flex items-baseline justify-between">
            <span className="text-[14px] font-medium">Staff you pay</span>
            <span className="num font-display text-[24px] font-semibold">{staff}</span>
          </span>
          <input type="range" min={1} max={500} value={staff} onChange={(e) => setStaff(Number(e.target.value))} className="accent-[var(--c-brand)]" />
        </label>
        <label className="grid gap-3">
          <span className="flex items-baseline justify-between">
            <span className="text-[14px] font-medium">Average monthly salary</span>
            <span className="num font-display text-[24px] font-semibold">{naira(salary * 100)}</span>
          </span>
          <input type="range" min={30_000} max={1_000_000} step={10_000} value={salary} onChange={(e) => setSalary(Number(e.target.value))} className="accent-[var(--c-brand)]" />
        </label>
        <p className="text-[13px] leading-6 text-ink-2">
          Your plan is picked by staff count, and the per-staff price drops as you grow. The {commission} service fee applies only to salaries you actually disburse — failed transfers are refunded in full, fees included.
        </p>
      </div>
      <div className="rounded-[22px] border border-line bg-raised p-6">
        <p className="text-[13px] text-ink-3">{plan.name} plan</p>
        <p className="mt-1 font-display text-[34px] font-semibold leading-none">
          {naira(subscription)}
          <span className="text-[14px] font-normal text-ink-3"> / month</span>
        </p>
        <p className="mt-2 text-[12.5px] text-ink-3">
          {naira(plan.base_fee_kobo)} base + {naira(plan.per_staff_kobo)} per staff
        </p>
        <dl className="mt-6 grid gap-2.5 border-t border-line pt-5 text-[13px]">
          <div className="flex justify-between"><dt className="text-ink-2">Service fee per payroll ({commission})</dt><dd className="num font-medium">{naira(commissionKobo)}</dd></div>
          <div className="flex justify-between"><dt className="text-ink-2">Paystack transfer fees</dt><dd className="num font-medium">{naira(fees)}</dd></div>
        </dl>
        <ButtonLink to="/signup" block size="lg" className="mt-6">
          Start free
        </ButtonLink>
      </div>
    </div>
  );
}

const FAQ = [
  ["Do my staff need a Streixpei account?", "No. They open your link or scan the QR code, enter the staff ID you gave them, and add their bank details. That's it — they get a confirmation and a payslip by email every payday."],
  ["What stops the wrong person registering?", "Only IDs on your list are accepted, each one works once, and every bank account is checked with the bank. If the account name doesn't match the name entered, we flag it for you before anyone is paid."],
  ["How do I put money in?", "Transfer to your workgroup's own account number, or pay by card, bank or USSD through Paystack. Paystack's fee is shown before you pay, and the exact amount you intended lands in your wallet."],
  ["What happens if a transfer fails?", "That staff member's salary, transfer fee and service fee go straight back to your wallet, and you can retry them in one click."],
  ["Can payroll run without me?", "Yes. Switch the workgroup to automatic and keep the wallet funded. On payday everyone is paid; if the wallet is short we email you the exact amount needed and pay as soon as it arrives."],
];

export default function Landing() {
  const { mode, toggleMode } = useTheme();
  const { user } = useAuth();
  const meta = useMeta();
  const plans = useQuery({ queryKey: ["plans"], queryFn: () => publicApi.get<Plan[]>("/plans"), staleTime: 10 * 60_000 });
  const commission = meta.data?.commission_label ?? "0.5%";
  const trial = meta.data?.trial_days ?? 14;

  return (
    <div className="min-h-screen overflow-x-hidden bg-shell text-ink">
      <header className="sticky top-0 z-50 border-b border-line bg-shell/85 backdrop-blur-xl">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center justify-between px-5 sm:px-8">
          <Logo />
          <nav className="hidden items-center gap-8 text-[14px] text-ink-2 md:flex" aria-label="Main">
            <a href="#how" className="hover:text-ink">How it works</a>
            <a href="#pricing" className="hover:text-ink">Pricing</a>
            <a href="#security" className="hover:text-ink">Security</a>
            <a href="#faq" className="hover:text-ink">Questions</a>
          </nav>
          <div className="flex items-center gap-2">
            <button type="button" onClick={toggleMode} aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"} className="flex h-10 w-10 items-center justify-center rounded-xl border border-line text-ink-2 hover:text-ink">
              {mode === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            {user ? (
              <ButtonLink to={user.role === "admin" ? "/admin" : "/app"}>Open dashboard</ButtonLink>
            ) : (
              <>
                <Link to="/login" className="hidden px-3 text-[14px] font-medium text-ink-2 hover:text-ink sm:block">
                  Sign in
                </Link>
                <ButtonLink to="/signup">Start free</ButtonLink>
              </>
            )}
          </div>
        </div>
      </header>

      <main>
        <section className="relative">
          <div className="pointer-events-none absolute left-1/2 top-[-260px] h-[620px] w-[920px] -translate-x-1/2 rounded-full bg-brand/10 blur-[150px]" />
          <div className="relative mx-auto grid max-w-6xl gap-14 px-5 pb-24 pt-16 sm:px-8 sm:pt-24 xl:grid-cols-[1fr_auto] xl:items-center xl:gap-12 lg:pb-32">
            <div>
              <h1 className="font-display text-[44px] font-semibold leading-[0.98] tracking-[-0.045em] sm:text-[64px] xl:text-[68px]">
                Pay your whole team from one link.
              </h1>
              <p className="mt-7 max-w-xl text-[17px] leading-8 text-ink-2">
                Give each staff member an ID and share one QR code. They register their own bank details — checked with their bank. You fund once, and Streixpei pays everyone, on payday or whenever you say.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <ButtonLink to="/signup" size="lg">
                  Start your {trial}-day free trial
                </ButtonLink>
                <a href="#pricing" className="inline-flex h-12 items-center rounded-2xl border border-line px-5 text-[15px] font-semibold text-ink-2 transition hover:border-line-strong hover:text-ink">
                  See pricing
                </a>
              </div>
              <p className="mt-5 text-[13px] text-ink-3">No card needed. Staff never need an account.</p>
            </div>
            <div className="flex items-start justify-center gap-4 xl:justify-end">
              <div className="hidden sm:mt-16 sm:block">
                <PhoneForm />
              </div>
              <HeroReceipt />
            </div>
          </div>
        </section>

        <section id="how" className="border-t border-line px-5 py-24 sm:px-8">
          <div className="mx-auto max-w-6xl">
            <h2 className="max-w-2xl font-display text-[36px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[48px]">From staff list to paid, in four steps.</h2>
            <ol className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {[
                [Building2, "Create a workgroup", "Name the business and say how many staff you pay. That's your plan, sorted."],
                [FileText, "Set up staff IDs", "Upload the employee numbers you already use, or let us generate a unique ID for each person."],
                [QrCode, "Share one link", "Print the QR poster or send the link on WhatsApp. Staff register in two minutes — no accounts."],
                [CalendarClock, "Fund and pay", "Transfer to your account number or pay by card, then disburse — or let payday run automatically."],
              ].map(([Icon, title, text], i) => {
                const I = Icon as typeof Building2;
                return (
                  <li key={title as string} className="rounded-[22px] border border-line bg-surface p-6">
                    <div className="flex items-center justify-between">
                      <I size={20} className="text-brand-strong dark:text-brand" />
                      <span className="num text-[13px] font-semibold text-ink-3">{i + 1}</span>
                    </div>
                    <h3 className="mt-10 text-[17px] font-semibold">{title as string}</h3>
                    <p className="mt-2 text-[14px] leading-6 text-ink-2">{text as string}</p>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <section className="px-5 pb-24 sm:px-8">
          <div className="mx-auto grid max-w-6xl gap-4 lg:grid-cols-[1.2fr_1fr]">
            <div className="rounded-[28px] border border-white/10 bg-[#100E0B] p-8 text-[#F6F1E8] sm:p-10">
              <Sparkles size={22} className="text-[#C4A15C]" />
              <h3 className="mt-8 font-display text-[30px] font-semibold leading-tight tracking-[-0.03em]">Tell SPI what to do. It does it.</h3>
              <p className="mt-3 max-w-md text-[15px] leading-7 text-[#F6F1E8]/65">
                Your payroll assistant reads your data and takes action — set salaries, generate IDs, prepare payroll, create a funding link. Anything that changes data waits for your confirmation; paying staff needs your password.
              </p>
              <div className="mt-8 grid gap-2.5 text-[14px]">
                <p className="ml-auto max-w-[80%] rounded-2xl rounded-br-md bg-[#F6F1E8] px-4 py-2.5 text-[#151412]">Move Amaka to Supervisors and prepare October payroll</p>
                <p className="max-w-[85%] rounded-2xl rounded-bl-md border border-white/10 bg-[#171411] px-4 py-2.5">
                  Done. Payroll PAY-2610 is ready for 48 staff — ₦8,466,900 including fees. Your wallet covers it.
                </p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              {[
                [BadgeCheck, "Bank-verified accounts", "Every account is resolved with the bank before it's saved. Mismatched names are flagged."],
                [FileText, "Receipts for everyone", "Staff get a payslip by email; you get a statement, CSV exports and a full audit trail."],
              ].map(([Icon, title, text]) => {
                const I = Icon as typeof BadgeCheck;
                return (
                  <div key={title as string} className="rounded-[22px] border border-line bg-surface p-6">
                    <I size={20} className="text-brand-strong dark:text-brand" />
                    <h3 className="mt-6 text-[16px] font-semibold">{title as string}</h3>
                    <p className="mt-1.5 text-[14px] leading-6 text-ink-2">{text as string}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section id="pricing" className="border-t border-line px-5 py-24 sm:px-8">
          <div className="mx-auto max-w-6xl">
            <div className="max-w-2xl">
              <h2 className="font-display text-[36px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[48px]">Priced by the number of staff you pay.</h2>
              <p className="mt-5 text-[16px] leading-7 text-ink-2">
                A monthly plan for your team size, a {commission} service fee on salaries disbursed, and Paystack's own fees passed through at cost — shown before every payment.
              </p>
            </div>
            <div className="mt-12">{plans.data && <PricingCalculator plans={plans.data} commission={commission} />}</div>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {(plans.data ?? []).map((p) => (
                <div key={p.code} className="rounded-[22px] border border-line bg-surface p-6">
                  <div className="flex items-baseline justify-between">
                    <h3 className="text-[18px] font-semibold">{p.name}</h3>
                    <span className="text-[12.5px] text-ink-3">
                      {p.min_staff}
                      {p.max_staff ? `–${p.max_staff}` : "+"} staff
                    </span>
                  </div>
                  <p className="mt-4 font-display text-[28px] font-semibold">
                    {naira(p.per_staff_kobo)}
                    <span className="text-[13px] font-normal text-ink-3"> per staff / month</span>
                  </p>
                  <p className="text-[12.5px] text-ink-3">+ {naira(p.base_fee_kobo)} base</p>
                  <ul className="mt-5 grid gap-2 text-[13.5px] text-ink-2">
                    {p.features.map((f) => (
                      <li key={f} className="flex gap-2">
                        <Check size={15} className="mt-0.5 shrink-0 text-brand-strong dark:text-brand" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="px-5 pb-24 sm:px-8">
          <div className="mx-auto max-w-6xl rounded-[28px] border border-line bg-surface p-8 sm:p-12">
            <ShieldCheck size={24} className="text-brand-strong dark:text-brand" />
            <h2 className="mt-6 max-w-2xl font-display text-[32px] font-semibold leading-[1.08] tracking-[-0.03em] sm:text-[42px]">Built so money only goes where it should.</h2>
            <div className="mt-10 grid gap-x-10 gap-y-6 md:grid-cols-2">
              {[
                ["One ID, one person", "Staff IDs are checked on every registration and can only be claimed once."],
                ["Payments through Paystack", "Collections and transfers run on Paystack's licensed rails. Card details never touch Streixpei."],
                ["Password to disburse", "Paying staff always needs the manager's password — even when SPI prepares it."],
                ["A ledger you can audit", "Every naira in and out of the wallet is recorded with a running balance and exportable statement."],
              ].map(([t, d]) => (
                <div key={t} className="flex gap-3">
                  <Check size={18} className="mt-0.5 shrink-0 text-good" />
                  <div>
                    <p className="text-[15px] font-semibold">{t}</p>
                    <p className="mt-1 text-[14px] leading-6 text-ink-2">{d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="faq" className="border-t border-line px-5 py-24 sm:px-8">
          <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[1fr_1.4fr]">
            <h2 className="font-display text-[36px] font-semibold leading-[1.05] tracking-[-0.035em] sm:text-[44px]">Questions finance teams ask us.</h2>
            <div className="divide-y divide-line border-y border-line">
              {FAQ.map(([q, a]) => (
                <details key={q} className="group py-5">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-[16px] font-semibold">
                    {q}
                    <span className={cx("text-[22px] font-normal text-ink-3 transition group-open:rotate-45")}>+</span>
                  </summary>
                  <p className="mt-3 max-w-2xl text-[14.5px] leading-7 text-ink-2">{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="px-5 pb-24 sm:px-8">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 rounded-[28px] bg-brand p-8 text-brand-ink sm:p-12 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="font-display text-[30px] font-semibold leading-tight tracking-[-0.03em] sm:text-[38px]">Run next month's payroll on Streixpei.</h2>
              <p className="mt-2 text-[15px] opacity-75">{trial} days free. Set up in an afternoon.</p>
            </div>
            <Link to="/signup" className="inline-flex h-12 shrink-0 items-center rounded-2xl bg-[#151412] px-6 text-[15px] font-semibold text-[#F6F1E8] transition hover:opacity-90">
              Create your account
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line px-5 py-10 sm:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 text-[13px] text-ink-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <Logo compact />
            <span>A Streixcorp company</span>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <a href="#pricing" className="hover:text-ink">Pricing</a>
            <a href="#security" className="hover:text-ink">Security</a>
            <a href={`mailto:${meta.data?.support_email ?? "support@streixpei.com"}`} className="hover:text-ink">Support</a>
            <span>© {new Date().getFullYear()} Streixcorp</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
