import type { ReactNode } from "react";
import { naira } from "../lib/format";
import { cx } from "./ui";

/** The payroll cost breakdown, styled like a printed receipt. */
export function Receipt({
  title,
  lines,
  total,
  footer,
  className,
}: {
  title: ReactNode;
  lines: { label: ReactNode; value: number; muted?: boolean }[];
  total: { label: ReactNode; value: number };
  footer?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cx("relative overflow-hidden rounded-[22px] border border-line bg-surface shadow-[var(--shadow-card)]", className)}>
      <div className="px-6 pb-5 pt-6">
        <p className="text-[13px] font-medium text-ink-3">{title}</p>
        <dl className="mt-4 grid gap-2.5">
          {lines.map((line, i) => (
            <div key={i} className="flex items-baseline justify-between gap-4 text-[13.5px]">
              <dt className={line.muted ? "text-ink-3" : "text-ink-2"}>{line.label}</dt>
              <dd className="num font-medium">{naira(line.value)}</dd>
            </div>
          ))}
        </dl>
        <div className="mt-4 border-t border-dashed border-line-strong pt-4">
          <div className="flex items-baseline justify-between gap-4">
            <span className="text-[14px] font-semibold">{total.label}</span>
            <span className="font-display text-[28px] font-semibold tracking-tight">{naira(total.value)}</span>
          </div>
        </div>
      </div>
      {footer && <div className="border-t border-line bg-soft/40 px-6 py-5">{footer}</div>}
    </div>
  );
}
