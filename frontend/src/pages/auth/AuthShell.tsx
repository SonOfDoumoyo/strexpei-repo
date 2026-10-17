import type { ReactNode } from "react";
import { Check } from "lucide-react";
import { Logo } from "../../components/Logo";

const LEDGER = [
  { name: "Chidi Eze", bank: "GTBank ••••6789", amount: "₦250,000" },
  { name: "Amaka Obi", bank: "Access ••••1043", amount: "₦180,000" },
  { name: "Ibrahim Bello", bank: "OPay ••••5521", amount: "₦120,000" },
  { name: "Funmi Adeyemi", bank: "Zenith ••••0918", amount: "₦120,000" },
];

export function AuthShell({ children, title, subtitle }: { children: ReactNode; title: string; subtitle?: ReactNode }) {
  return (
    <div className="grid min-h-screen bg-shell lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <aside className="relative hidden overflow-hidden bg-[#100E0B] p-10 text-[#F6F1E8] lg:flex lg:flex-col">
        <div className="pointer-events-none absolute -left-40 top-1/3 h-[520px] w-[520px] rounded-full bg-[#C4A15C]/10 blur-[120px]" />
        <Logo tone="light" />
        <div className="relative mt-auto max-w-md">
          <p className="font-display text-[44px] font-semibold leading-[1.02] tracking-[-0.04em]">Every salary, sent from one wallet.</p>
          <p className="mt-4 text-[14.5px] leading-7 text-[#F6F1E8]/60">
            Staff register with the ID you give them. You fund once and pay everyone — with a receipt in each inbox.
          </p>
          <div className="mt-10 overflow-hidden rounded-[22px] border border-white/10 bg-[#171411]">
            <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-3.5 text-[12.5px]">
              <span className="font-semibold">October payroll</span>
              <span className="text-[#F6F1E8]/45">4 of 4 paid</span>
            </div>
            {LEDGER.map((row) => (
              <div key={row.name} className="flex items-center gap-3 border-b border-white/[0.06] px-5 py-3 last:border-0">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#5fbf8a]/15 text-[#5fbf8a]">
                  <Check size={13} strokeWidth={2.6} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13.5px] font-medium">{row.name}</span>
                  <span className="block text-[12px] text-[#F6F1E8]/40">{row.bank}</span>
                </span>
                <span className="num text-[13.5px] font-semibold">{row.amount}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
      <main className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 lg:hidden">
            <Logo />
          </div>
          <h1 className="text-[32px] font-semibold leading-tight">{title}</h1>
          {subtitle && <div className="mt-2 text-[14.5px] leading-6 text-ink-2">{subtitle}</div>}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}
