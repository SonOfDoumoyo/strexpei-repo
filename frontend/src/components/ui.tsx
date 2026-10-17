import {
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { AlertTriangle, Check, CheckCircle2, ChevronDown, Copy, Info, Loader2, X, XCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { formatTypedNaira, initials, parseNaira, toNairaInput } from "../lib/format";

export const cx = (...parts: (string | false | null | undefined)[]) => parts.filter(Boolean).join(" ");

// ---------------------------------------------------------------- button
type Variant = "primary" | "dark" | "secondary" | "soft" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const variants: Record<Variant, string> = {
  primary: "bg-brand text-brand-ink hover:bg-brand-strong shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)]",
  dark: "bg-ink text-shell hover:opacity-90",
  secondary: "bg-raised text-ink border border-line hover:border-line-strong",
  soft: "bg-soft text-ink hover:bg-brand-soft hover:brightness-[0.98]",
  ghost: "text-ink-2 hover:bg-ink/5 hover:text-ink",
  danger: "bg-bad text-white hover:opacity-90",
};
const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-[13px] gap-1.5 rounded-xl",
  md: "h-11 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-5 text-[15px] gap-2 rounded-2xl",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size; loading?: boolean; icon?: ReactNode; block?: boolean };

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading = false, icon, block, className, children, disabled, type = "button", ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex shrink-0 select-none items-center justify-center font-semibold transition-[background,opacity,border-color,transform] active:translate-y-px disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        block && "w-full",
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 size={size === "sm" ? 14 : 16} className="animate-spin" /> : icon}
      {children}
    </button>
  );
});

export function ButtonLink({ to, variant = "primary", size = "md", icon, className, children, block }: { to: string; variant?: Variant; size?: Size; icon?: ReactNode; className?: string; children: ReactNode; block?: boolean }) {
  return (
    <Link to={to} className={cx("inline-flex shrink-0 items-center justify-center font-semibold transition", variants[variant], sizes[size], block && "w-full", className)}>
      {icon}
      {children}
    </Link>
  );
}

export function IconButton({ label, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button type="button" aria-label={label} title={label} className={cx("inline-flex h-9 w-9 items-center justify-center rounded-xl text-ink-2 transition hover:bg-ink/5 hover:text-ink", className)} {...rest}>
      {children}
    </button>
  );
}

// ------------------------------------------------------------------ card
export function Card({ className, children, as: As = "section" }: { className?: string; children: ReactNode; as?: "section" | "div" | "article" }) {
  return <As className={cx("card", className)}>{children}</As>;
}

export function CardHeader({ title, description, action, className }: { title: ReactNode; description?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4 sm:px-6", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
        {description && <p className="mt-0.5 text-[13px] text-ink-3">{description}</p>}
      </div>
      {action}
    </div>
  );
}

// ----------------------------------------------------------- page header
export function PageHeader({ title, description, action, back }: { title: ReactNode; description?: ReactNode; action?: ReactNode; back?: { to: string; label: string } }) {
  return (
    <header className="mb-6 flex flex-col gap-4 sm:mb-8 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        {back && (
          <Link to={back.to} className="mb-3 inline-flex items-center gap-1 text-[13px] font-medium text-ink-3 hover:text-ink">
            ← {back.label}
          </Link>
        )}
        <h1 className="text-[28px] font-semibold leading-[1.1] sm:text-[34px]">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-[14px] leading-6 text-ink-2">{description}</p>}
      </div>
      {action && <div className="flex flex-wrap items-center gap-2">{action}</div>}
    </header>
  );
}

// ---------------------------------------------------------------- fields
export function Field({ label, hint, error, children, htmlFor, optional, className }: { label: ReactNode; hint?: ReactNode; error?: string | null; children: ReactNode; htmlFor?: string; optional?: boolean; className?: string }) {
  return (
    <div className={cx("grid gap-1.5", className)}>
      <label htmlFor={htmlFor} className="flex items-baseline justify-between gap-2 text-[13px] font-medium text-ink">
        <span>{label}</span>
        {optional && <span className="text-[12px] font-normal text-ink-3">Optional</span>}
      </label>
      {children}
      {error ? (
        <p role="alert" className="text-[12px] font-medium text-bad">
          {error}
        </p>
      ) : (
        hint && <p className="text-[12px] leading-5 text-ink-3">{hint}</p>
      )}
    </div>
  );
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label?: ReactNode; hint?: ReactNode; error?: string | null; optional?: boolean; leading?: ReactNode; trailing?: ReactNode };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, hint, error, optional, leading, trailing, className, id, ...rest }, ref) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const control = (
    <div className="relative">
      {leading && <span className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-ink-3">{leading}</span>}
      <input ref={ref} id={inputId} aria-invalid={error ? true : undefined} className={cx("input", leading ? "pl-10" : "", trailing ? "pr-11" : "", className)} {...rest} />
      {trailing && <span className="absolute inset-y-0 right-2 flex items-center">{trailing}</span>}
    </div>
  );
  if (!label) return control;
  return (
    <Field label={label} hint={hint} error={error} htmlFor={inputId} optional={optional}>
      {control}
    </Field>
  );
});

export function MoneyInput({ label, hint, error, valueKobo, onChangeKobo, optional, placeholder = "0", id, autoFocus, disabled }: { label?: ReactNode; hint?: ReactNode; error?: string | null; valueKobo: number | null; onChangeKobo: (kobo: number | null) => void; optional?: boolean; placeholder?: string; id?: string; autoFocus?: boolean; disabled?: boolean }) {
  const [text, setText] = useState(() => toNairaInput(valueKobo));
  const last = useRef(valueKobo);
  useEffect(() => {
    if (valueKobo !== last.current) {
      last.current = valueKobo;
      setText(toNairaInput(valueKobo));
    }
  }, [valueKobo]);
  return (
    <Input
      id={id}
      label={label}
      hint={hint}
      error={error}
      optional={optional}
      inputMode="decimal"
      autoComplete="off"
      autoFocus={autoFocus}
      disabled={disabled}
      placeholder={placeholder}
      leading={<span className="text-[14px] font-semibold text-ink-2">₦</span>}
      className="num font-medium"
      value={text}
      onChange={(e) => {
        const formatted = formatTypedNaira(e.target.value);
        setText(formatted);
        const kobo = parseNaira(formatted);
        last.current = kobo;
        onChangeKobo(kobo);
      }}
    />
  );
}

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement> & { label?: ReactNode; hint?: ReactNode; error?: string | null }>(function Select(
  { label, hint, error, className, id, children, ...rest },
  ref,
) {
  const autoId = useId();
  const selectId = id ?? autoId;
  const control = (
    <div className="relative">
      <select ref={ref} id={selectId} aria-invalid={error ? true : undefined} className={cx("input appearance-none pr-10", className)} {...rest}>
        {children}
      </select>
      <ChevronDown size={16} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-ink-3" />
    </div>
  );
  if (!label) return control;
  return (
    <Field label={label} hint={hint} error={error} htmlFor={selectId}>
      {control}
    </Field>
  );
});

export function Textarea({ label, hint, error, className, id, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { label?: ReactNode; hint?: ReactNode; error?: string | null }) {
  const autoId = useId();
  const tid = id ?? autoId;
  const control = <textarea id={tid} className={cx("input min-h-28 py-3 leading-6", className)} {...rest} />;
  if (!label) return control;
  return (
    <Field label={label} hint={hint} error={error} htmlFor={tid}>
      {control}
    </Field>
  );
}

export function Toggle({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label?: ReactNode; description?: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="group flex w-full items-center justify-between gap-4 text-left disabled:opacity-50"
    >
      {(label || description) && (
        <span className="min-w-0">
          {label && <span className="block text-[14px] font-medium">{label}</span>}
          {description && <span className="mt-0.5 block text-[12.5px] leading-5 text-ink-3">{description}</span>}
        </span>
      )}
      <span className={cx("relative h-6 w-11 shrink-0 rounded-full transition", checked ? "bg-brand" : "bg-ink/15")}>
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-[22px]" : "translate-x-0.5")} />
      </span>
    </button>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "md", className }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; count?: number }[]; size?: "sm" | "md"; className?: string }) {
  return (
    <div role="tablist" className={cx("inline-flex rounded-xl border border-line bg-soft/60 p-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          type="button"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            "inline-flex items-center gap-1.5 rounded-lg font-medium transition",
            size === "sm" ? "h-7 px-2.5 text-[12.5px]" : "h-8 px-3 text-[13px]",
            value === o.value ? "bg-raised text-ink shadow-sm" : "text-ink-3 hover:text-ink",
          )}
        >
          {o.label}
          {o.count !== undefined && <span className={cx("num rounded-md px-1.5 text-[11px]", value === o.value ? "bg-soft text-ink-2" : "text-ink-3")}>{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- status
type Tone = "good" | "warn" | "bad" | "brand" | "neutral" | "muted" | "info";
const tones: Record<Tone, string> = {
  good: "bg-good-soft text-good",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  brand: "bg-brand-soft text-brand-strong dark:text-brand",
  neutral: "bg-soft text-ink-2",
  muted: "bg-ink/5 text-ink-3",
  info: "bg-series-2/10 text-series-2",
};

export function Badge({ tone = "neutral", children, className, dot = true }: { tone?: Tone; children: ReactNode; className?: string; dot?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold", tones[tone], className)}>
      {dot && <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  );
}

const STATUS: Record<string, [string, Tone]> = {
  registered: ["Registered", "good"],
  pending: ["Unclaimed", "neutral"],
  inactive: ["Inactive", "muted"],
  draft: ["Draft", "neutral"],
  awaiting_funding: ["Awaiting funds", "warn"],
  ready: ["Ready to pay", "brand"],
  processing: ["Paying", "info"],
  completed: ["Paid", "good"],
  partially_failed: ["Partly paid", "warn"],
  failed: ["Failed", "bad"],
  canceled: ["Cancelled", "muted"],
  queued: ["Queued", "neutral"],
  success: ["Paid", "good"],
  reversed: ["Reversed", "bad"],
  trialing: ["Free trial", "brand"],
  active: ["Active", "good"],
  past_due: ["Payment due", "warn"],
  expired: ["Expired", "bad"],
  paid: ["Paid", "good"],
  void: ["Void", "muted"],
  abandoned: ["Not completed", "muted"],
  suspended: ["Suspended", "bad"],
  deleted: ["Deleted", "muted"],
};

export function StatusPill({ status, label }: { status: string; label?: string }) {
  const [text, tone] = STATUS[status] ?? [status.replace(/_/g, " "), "neutral"];
  return <Badge tone={tone}>{label ?? text}</Badge>;
}

export function Notice({ tone = "info", title, children, action, className }: { tone?: "info" | "good" | "warn" | "bad"; title?: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  const Icon = { info: Info, good: CheckCircle2, warn: AlertTriangle, bad: XCircle }[tone];
  const color = { info: "text-brand-strong dark:text-brand", good: "text-good", warn: "text-warn", bad: "text-bad" }[tone];
  const bg = { info: "bg-brand-soft/70 border-brand/20", good: "bg-good-soft border-good/20", warn: "bg-warn-soft border-warn/25", bad: "bg-bad-soft border-bad/25" }[tone];
  return (
    <div role={tone === "bad" ? "alert" : "status"} className={cx("flex flex-col gap-3 rounded-2xl border p-4 sm:flex-row sm:items-center", bg, className)}>
      <div className="flex min-w-0 flex-1 gap-3">
        <Icon size={18} className={cx("mt-0.5 shrink-0", color)} />
        <div className="min-w-0 text-[13.5px] leading-6">
          {title && <p className="font-semibold text-ink">{title}</p>}
          {children && <div className="text-ink-2">{children}</div>}
        </div>
      </div>
      {action && <div className="flex shrink-0 gap-2 pl-7 sm:pl-0">{action}</div>}
    </div>
  );
}

// ----------------------------------------------------------------- misc
export function Spinner({ size = 18, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={cx("animate-spin text-ink-3", className)} aria-label="Loading" />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function PageLoader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="grid gap-4" aria-busy="true" aria-label={label}>
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-[22px]" />
        ))}
      </div>
      <Skeleton className="h-72 rounded-[22px]" />
    </div>
  );
}

export function EmptyState({ icon, title, children, action, className }: { icon?: ReactNode; title: ReactNode; children?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cx("flex flex-col items-center justify-center px-6 py-14 text-center", className)}>
      {icon && <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-soft text-brand-strong dark:text-brand">{icon}</div>}
      <h3 className="text-[16px] font-semibold">{title}</h3>
      {children && <div className="mt-1.5 max-w-sm text-[13.5px] leading-6 text-ink-2">{children}</div>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  return (
    <EmptyState icon={<XCircle size={20} />} title="This didn't load" action={onRetry && <Button variant="secondary" onClick={onRetry}>Try again</Button>}>
      {message}
    </EmptyState>
  );
}

export function Avatar({ name, size = 36, className }: { name?: string | null; size?: number; className?: string }) {
  return (
    <span
      className={cx("inline-flex shrink-0 items-center justify-center rounded-xl bg-soft font-semibold text-ink-2", className)}
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

export function Stat({ label, value, sub, icon, action, tone }: { label: ReactNode; value: ReactNode; sub?: ReactNode; icon?: ReactNode; action?: ReactNode; tone?: "warn" | "good" | "bad" }) {
  return (
    <div className="card flex flex-col p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[13px] font-medium text-ink-2">{label}</p>
        {icon && <span className="text-ink-3">{icon}</span>}
      </div>
      <p className={cx("mt-3 font-display text-[26px] font-semibold leading-none tracking-tight", tone === "warn" && "text-warn", tone === "bad" && "text-bad", tone === "good" && "text-good")}>{value}</p>
      {(sub || action) && (
        <div className="mt-3 flex items-end justify-between gap-2">
          {sub && <p className="text-[12.5px] leading-5 text-ink-3">{sub}</p>}
          {action}
        </div>
      )}
    </div>
  );
}

export function Progress({ value, max, tone = "brand", className, label }: { value: number; max: number; tone?: "brand" | "good" | "warn"; className?: string; label?: string }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className={cx("h-2 overflow-hidden rounded-full bg-ink/8", className)} role="progressbar" aria-valuenow={value} aria-valuemax={max} aria-label={label}>
      <div className={cx("h-full rounded-full transition-[width] duration-500", tone === "good" ? "bg-good" : tone === "warn" ? "bg-warn" : "bg-brand")} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function CopyButton({ text, label = "Copy", className, size = "sm", variant = "secondary" }: { text: string; label?: string; className?: string; size?: Size; variant?: Variant }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant={variant}
      size={size}
      className={className}
      icon={copied ? <Check size={14} /> : <Copy size={14} />}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
        } catch {
          const area = document.createElement("textarea");
          area.value = text;
          document.body.appendChild(area);
          area.select();
          document.execCommand("copy");
          area.remove();
        }
        setCopied(true);
        setTimeout(() => setCopied(false), 1600);
      }}
    >
      {copied ? "Copied" : label}
    </Button>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-3 text-[13px] text-ink-3">
      <span className="num">
        {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)} of {total.toLocaleString()}
      </span>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Previous
        </Button>
        <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}

// ------------------------------------------------------- modal / drawer
function useLockScroll(open: boolean) {
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);
}

function useEscape(open: boolean, onClose: () => void) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);
}

function useAutoFocus(open: boolean) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || !ref.current) return;
    const el = ref.current.querySelector<HTMLElement>("[autofocus], input:not([type=hidden]), select, textarea, button[data-primary]");
    (el ?? ref.current).focus();
  }, [open]);
  return ref;
}

export function Modal({ open, onClose, title, description, children, footer, size = "md" }: { open: boolean; onClose: () => void; title: ReactNode; description?: ReactNode; children?: ReactNode; footer?: ReactNode; size?: "sm" | "md" | "lg" }) {
  useLockScroll(open);
  useEscape(open, onClose);
  const ref = useAutoFocus(open);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[300] flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div className="animate-fade absolute inset-0 bg-[#0b0906]/50 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
        className={cx(
          "animate-pop relative flex max-h-[92vh] w-full flex-col overflow-hidden rounded-t-[26px] border border-line bg-surface shadow-[var(--shadow-pop)] outline-none sm:rounded-[24px]",
          size === "sm" ? "sm:max-w-md" : size === "lg" ? "sm:max-w-3xl" : "sm:max-w-xl",
        )}
      >
        <div className="flex items-start justify-between gap-4 px-6 pb-2 pt-6">
          <div>
            <h2 className="text-[19px] font-semibold">{title}</h2>
            {description && <p className="mt-1 text-[13.5px] leading-6 text-ink-2">{description}</p>}
          </div>
          <IconButton label="Close" onClick={onClose} className="-mr-2 -mt-1">
            <X size={18} />
          </IconButton>
        </div>
        <div className="scrollbar-thin overflow-y-auto px-6 pb-6 pt-3">{children}</div>
        {footer && <div className="flex flex-col-reverse gap-2 border-t border-line bg-soft/40 px-6 py-4 sm:flex-row sm:justify-end">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, title, subtitle, children, footer }: { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  useLockScroll(open);
  useEscape(open, onClose);
  const ref = useAutoFocus(open);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[250]">
      <div className="animate-fade absolute inset-0 bg-[#0b0906]/40" onClick={onClose} />
      <aside ref={ref} tabIndex={-1} role="dialog" aria-modal="true" className="animate-slide absolute inset-y-0 right-0 flex w-full max-w-[480px] flex-col border-l border-line bg-surface shadow-[var(--shadow-pop)] outline-none">
        <div className="flex items-start justify-between gap-3 border-b border-line px-6 py-5">
          <div className="min-w-0">
            <h2 className="truncate text-[19px] font-semibold">{title}</h2>
            {subtitle && <div className="mt-1 text-[13px] text-ink-3">{subtitle}</div>}
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X size={18} />
          </IconButton>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">{children}</div>
        {footer && <div className="border-t border-line px-6 py-4">{footer}</div>}
      </aside>
    </div>,
    document.body,
  );
}

// ------------------------------------------------------------- menu
export function Menu({ trigger, children, align = "right", width = 240, side = "bottom" }: { trigger: (props: { open: boolean; toggle: () => void }) => ReactNode; children: (close: () => void) => ReactNode; align?: "left" | "right"; width?: number; side?: "bottom" | "top" }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", handler);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  return (
    <div ref={ref} className="relative">
      {trigger({ open, toggle: () => setOpen((v) => !v) })}
      {open && (
        <div
          role="menu"
          className={cx("animate-pop absolute z-[120] overflow-hidden rounded-2xl border border-line bg-raised p-1.5 shadow-[var(--shadow-pop)]", side === "top" ? "bottom-full mb-2" : "mt-2", align === "right" ? "right-0" : "left-0")}
          style={{ width }}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function MenuItem({ onClick, children, icon, danger, to }: { onClick?: () => void; children: ReactNode; icon?: ReactNode; danger?: boolean; to?: string }) {
  const cls = cx("flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-[13.5px] font-medium transition hover:bg-soft", danger ? "text-bad" : "text-ink");
  if (to)
    return (
      <Link role="menuitem" to={to} onClick={onClick} className={cls}>
        {icon}
        {children}
      </Link>
    );
  return (
    <button role="menuitem" type="button" onClick={onClick} className={cls}>
      {icon}
      {children}
    </button>
  );
}

// -------------------------------------------------------------- table
export function Table({ children, className, minWidth = 640 }: { children: ReactNode; className?: string; minWidth?: number }) {
  return (
    <div className={cx("scrollbar-thin overflow-x-auto", className)}>
      <table className="w-full border-collapse text-left text-[13.5px]" style={{ minWidth }}>{children}</table>
    </div>
  );
}

export function Th({ children, className, align }: { children?: ReactNode; className?: string; align?: "right" | "left" }) {
  return <th className={cx("whitespace-nowrap border-b border-line bg-soft/40 px-5 py-2.5 text-[12px] font-semibold text-ink-3", align === "right" && "text-right", className)}>{children}</th>;
}

export function Td({ children, className, align }: { children?: ReactNode; className?: string; align?: "right" | "left" }) {
  return <td className={cx("border-b border-line px-5 py-3.5 align-middle", align === "right" && "num text-right", className)}>{children}</td>;
}

export function KeyValue({ rows, className }: { rows: [ReactNode, ReactNode][]; className?: string }) {
  return (
    <dl className={cx("divide-y divide-line", className)}>
      {rows.map(([k, v], i) => (
        <div key={i} className="flex items-start justify-between gap-4 py-2.5 text-[13.5px]">
          <dt className="text-ink-3">{k}</dt>
          <dd className="text-right font-medium text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
