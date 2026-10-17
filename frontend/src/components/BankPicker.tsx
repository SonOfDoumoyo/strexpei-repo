import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import type { Bank } from "../lib/types";
import { cx, Field } from "./ui";

const POPULAR = ["058", "044", "057", "033", "011", "070", "214", "035", "232", "999992", "999991", "50515", "50211"];

/** Searchable bank list — Paystack returns 100+ Nigerian banks. */
export function BankPicker({ banks, value, onChange, label = "Bank", error, loading }: { banks: Bank[]; value: string; onChange: (code: string) => void; label?: string; error?: string | null; loading?: boolean }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const listId = useId();
  const selected = banks.find((b) => b.code === value);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      const popular = POPULAR.map((c) => banks.find((b) => b.code === c)).filter(Boolean) as Bank[];
      const rest = banks.filter((b) => !POPULAR.includes(b.code));
      return [...popular, ...rest];
    }
    return banks.filter((b) => b.name.toLowerCase().includes(q));
  }, [banks, query]);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const choose = (bank: Bank) => {
    onChange(bank.code);
    setOpen(false);
    setQuery("");
  };

  return (
    <Field label={label} error={error}>
      <div ref={ref} className="relative">
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className={cx("input flex items-center justify-between text-left", !selected && "text-ink-3")}
        >
          <span className="truncate">{loading ? "Loading banks…" : selected?.name ?? "Choose your bank"}</span>
          <ChevronDown size={16} className="shrink-0 text-ink-3" />
        </button>
        {open && (
          <div className="animate-pop absolute left-0 right-0 z-50 mt-2 overflow-hidden rounded-2xl border border-line bg-raised shadow-[var(--shadow-pop)]">
            <div className="flex items-center gap-2 border-b border-line px-3">
              <Search size={15} className="text-ink-3" />
              <input
                autoFocus
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") {
                    e.preventDefault();
                    setActive((a) => Math.min(results.length - 1, a + 1));
                  } else if (e.key === "ArrowUp") {
                    e.preventDefault();
                    setActive((a) => Math.max(0, a - 1));
                  } else if (e.key === "Enter") {
                    e.preventDefault();
                    if (results[active]) choose(results[active]);
                  } else if (e.key === "Escape") setOpen(false);
                }}
                placeholder="Search banks"
                aria-controls={listId}
                className="h-11 flex-1 bg-transparent text-[14px] outline-none placeholder:text-ink-3"
              />
            </div>
            <ul id={listId} role="listbox" className="max-h-64 overflow-y-auto p-1.5">
              {results.length === 0 && <li className="px-3 py-3 text-[13px] text-ink-3">No bank matches “{query}”.</li>}
              {results.map((b, i) => (
                <li key={b.code} role="option" aria-selected={b.code === value}>
                  <button
                    type="button"
                    onMouseEnter={() => setActive(i)}
                    onClick={() => choose(b)}
                    className={cx("w-full rounded-xl px-3 py-2.5 text-left text-[14px]", i === active ? "bg-soft" : "", b.code === value && "font-semibold")}
                  >
                    {b.name}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Field>
  );
}
