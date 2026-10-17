import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cx } from "./ui";

type Toast = { id: number; tone: "success" | "error" | "info"; title: string; body?: string };
type Ctx = { success: (title: string, body?: string) => void; error: (title: string | unknown, body?: string) => void; info: (title: string, body?: string) => void };

const ToastContext = createContext<Ctx | null>(null);
let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback(
    (tone: Toast["tone"], title: string, body?: string) => {
      const id = ++seq;
      setToasts((t) => [...t.slice(-3), { id, tone, title, body }]);
      setTimeout(() => dismiss(id), tone === "error" ? 7000 : 4200);
    },
    [dismiss],
  );
  const value = useMemo<Ctx>(
    () => ({
      success: (title, body) => push("success", title, body),
      info: (title, body) => push("info", title, body),
      error: (title, body) => push("error", typeof title === "string" ? title : title instanceof Error ? title.message : "Something went wrong.", body),
    }),
    [push],
  );
  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-0 z-[400] flex flex-col items-center gap-2 p-4 sm:bottom-auto sm:left-auto sm:right-0 sm:top-0 sm:items-end">
          {toasts.map((t) => {
            const Icon = t.tone === "success" ? CheckCircle2 : t.tone === "error" ? XCircle : Info;
            return (
              <div key={t.id} role={t.tone === "error" ? "alert" : "status"} className="animate-pop pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-2xl border border-line bg-raised p-4 shadow-[var(--shadow-pop)]">
                <Icon size={18} className={cx("mt-0.5 shrink-0", t.tone === "success" ? "text-good" : t.tone === "error" ? "text-bad" : "text-brand")} />
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-semibold leading-5">{t.title}</p>
                  {t.body && <p className="mt-0.5 text-[13px] leading-5 text-ink-2">{t.body}</p>}
                </div>
                <button type="button" onClick={() => dismiss(t.id)} aria-label="Dismiss" className="-m-1 rounded-lg p-1 text-ink-3 hover:text-ink">
                  <X size={15} />
                </button>
              </div>
            );
          })}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
