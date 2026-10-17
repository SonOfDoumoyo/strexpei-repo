import { Link } from "react-router-dom";
import { cx } from "./ui";

export function LogoMark({ size = 30, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="9" fill="#151412" />
      <path d="M21.5 10H13.25a3.25 3.25 0 0 0 0 6.5h5.5a3.25 3.25 0 0 1 0 6.5H10.5" fill="none" stroke="#C4A15C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** STREIXPEI wordmark. `tone="light"` for dark backgrounds. */
export function Logo({ to = "/", tone, className, compact = false }: { to?: string | null; tone?: "light" | "dark"; className?: string; compact?: boolean }) {
  const content = (
    <span className={cx("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={compact ? 28 : 30} className={tone === "light" ? "ring-1 ring-white/10 rounded-[9px]" : "dark:ring-1 dark:ring-white/10 rounded-[9px]"} />
      <span
        className={cx(
          "font-display text-[17px] font-bold leading-none tracking-[0.14em]",
          tone === "light" ? "text-[#F6F1E8]" : tone === "dark" ? "text-[#151412]" : "text-ink",
        )}
      >
        STREIXPEI
      </span>
    </span>
  );
  if (to === null) return content;
  return (
    <Link to={to} aria-label="Streixpei home" className="inline-flex rounded-lg">
      {content}
    </Link>
  );
}
