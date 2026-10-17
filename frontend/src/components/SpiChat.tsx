import { type FormEvent, Fragment, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ArrowUp, Check, LockKeyhole, Sparkles, X } from "lucide-react";
import { api } from "../lib/api";
import type { AIAction, AIMessage, AIQuota } from "../lib/types";
import { Button, cx, Spinner } from "./ui";
import { useToast } from "./toast";

type Conversation = { conversation_id: string | null; messages: AIMessage[]; actions: AIAction[]; quota: AIQuota; mode: "ai" | "basic" };
type ChatResponse = { conversation_id: string; reply: string; actions: AIAction[]; navigate: string | null; mode: "ai" | "basic"; quota: AIQuota };

const SUGGESTIONS = [
  "How much will this month's payroll cost?",
  "Who hasn't registered yet?",
  "Generate 5 staff IDs",
  "What's my wallet balance?",
  "Show failed payments",
  "Switch payroll to automatic on the 28th",
];

function renderInline(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|https?:\/\/[^\s)]+|\/app\/[\w\-/?=&]+)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = pattern.exec(text))) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const token = m[0];
    if (token.startsWith("**")) parts.push(<strong key={i++}>{token.slice(2, -2)}</strong>);
    else
      parts.push(
        <a key={i++} href={token} target={token.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className="break-all font-medium text-brand-strong underline underline-offset-2 dark:text-brand">
          {token.startsWith("http") ? token.replace(/^https?:\/\//, "").slice(0, 48) + (token.length > 56 ? "…" : "") : token}
        </a>,
      );
    last = m.index + token.length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function RichText({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      blocks.push(
        <ul key={blocks.length} className="my-1 grid gap-1 pl-4">
          {list.map((l, i) => (
            <li key={i} className="list-disc marker:text-ink-3">
              {renderInline(l)}
            </li>
          ))}
        </ul>,
      );
      list = [];
    }
  };
  lines.forEach((line) => {
    const item = /^\s*(?:[-•*]|\d+\.)\s+(.*)$/.exec(line);
    if (item) list.push(item[1]);
    else {
      flush();
      if (line.trim()) blocks.push(<p key={blocks.length}>{renderInline(line)}</p>);
    }
  });
  flush();
  return <div className="grid gap-1.5">{blocks}</div>;
}

function ActionCard({ action, onResolved }: { action: AIAction; onResolved: (a: AIAction, message: string) => void }) {
  const [password, setPassword] = useState("");
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: (confirm: boolean) => api.post<{ action: AIAction; message: string }>(`/ai/actions/${action.id}`, { confirm, password: password || undefined }),
    onSuccess: (data) => onResolved(data.action, data.message),
    onError: (e) => toast.error(e),
  });
  const done = action.status !== "pending";
  return (
    <div className={cx("rounded-2xl border p-4", done ? "border-line bg-soft/40" : "border-brand/40 bg-brand-soft/50")}>
      <div className="flex items-start gap-3">
        <span className={cx("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg", done ? "bg-ink/5 text-ink-3" : "bg-brand text-brand-ink")}>
          {action.status === "executed" ? <Check size={15} /> : action.status === "pending" ? <Sparkles size={14} /> : <X size={15} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-[13.5px] font-semibold leading-5">{action.summary}</p>
          <p className="mt-0.5 text-[12px] text-ink-3">
            {action.status === "pending" ? "Waiting for your confirmation" : action.status === "executed" ? "Done" : action.status === "failed" ? String(action.result?.error ?? "Failed") : action.status === "canceled" ? "Cancelled" : "Expired"}
          </p>
          {!done && (
            <div className="mt-3 grid gap-2">
              {action.requires_password && (
                <div className="relative">
                  <LockKeyhole size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
                  <input type="password" className="input h-10 pl-9" placeholder="Your password to confirm payment" value={password} autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} />
                </div>
              )}
              <div className="flex gap-2">
                <Button size="sm" loading={mutation.isPending && mutation.variables === true} disabled={action.requires_password && !password} onClick={() => mutation.mutate(true)}>
                  Confirm
                </Button>
                <Button size="sm" variant="ghost" disabled={mutation.isPending} onClick={() => mutation.mutate(false)}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function SpiChat({ workgroupId, onNavigate, compact = false, initialPrompt }: { workgroupId: string | null; onNavigate?: () => void; compact?: boolean; initialPrompt?: string | null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const key = ["ai", workgroupId ?? "none"];
  const conversation = useQuery({
    queryKey: key,
    queryFn: () => api.get<Conversation>("/ai/conversation", workgroupId ? { workgroup_id: workgroupId } : undefined),
  });
  const [input, setInput] = useState("");
  const [optimistic, setOptimistic] = useState<AIMessage | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const sentInitial = useRef<string | null>(null);

  const send = useMutation({
    mutationFn: (message: string) =>
      api.post<ChatResponse>("/ai/chat", { message, workgroup_id: workgroupId ?? undefined, conversation_id: conversation.data?.conversation_id ?? undefined }),
    onMutate: (message) => setOptimistic({ id: "pending", role: "user", text: message, created_at: new Date().toISOString() }),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: key });
      setOptimistic(null);
      if (data.navigate) {
        navigate(data.navigate);
        onNavigate?.();
      }
      if (data.actions.some((a) => a.kind !== "confirm")) refreshAppData();
    },
    onError: (e) => {
      setOptimistic(null);
      toast.error(e);
    },
  });

  function refreshAppData() {
    queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] === "wg" || q.queryKey[0] === "workgroups" });
  }

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [conversation.data, optimistic, send.isPending]);

  useEffect(() => {
    if (initialPrompt && conversation.isSuccess && sentInitial.current !== initialPrompt && !send.isPending) {
      sentInitial.current = initialPrompt;
      send.mutate(initialPrompt);
    }
  }, [initialPrompt, conversation.isSuccess, send]);

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const text = input.trim();
    if (!text || send.isPending) return;
    setInput("");
    send.mutate(text);
  }

  const timeline = useMemo(() => {
    const data = conversation.data;
    if (!data) return [];
    const msgs = [...data.messages];
    if (optimistic) msgs.push(optimistic);
    const actions = [...data.actions].sort((a, b) => a.created_at.localeCompare(b.created_at));
    const used = new Set<string>();
    const rows: ({ kind: "msg"; m: AIMessage } | { kind: "action"; a: AIAction })[] = [];
    msgs.forEach((m) => {
      rows.push({ kind: "msg", m });
      if (m.role === "assistant") {
        actions.filter((a) => !used.has(a.id) && a.created_at <= m.created_at).forEach((a) => {
          used.add(a.id);
          rows.push({ kind: "action", a });
        });
      }
    });
    actions.filter((a) => !used.has(a.id)).forEach((a) => rows.push({ kind: "action", a }));
    return rows;
  }, [conversation.data, optimistic]);

  const quota = conversation.data?.quota;
  const empty = timeline.length === 0 && !send.isPending;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} className={cx("scrollbar-thin flex-1 overflow-y-auto", compact ? "px-5 py-5" : "px-5 py-6 sm:px-7")}>
        {conversation.isLoading ? (
          <div className="grid h-full place-items-center">
            <Spinner />
          </div>
        ) : empty ? (
          <div className="flex h-full flex-col justify-end gap-5 pb-2">
            <div>
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-ink text-brand dark:bg-raised">
                <Sparkles size={20} />
              </span>
              <h3 className="mt-4 text-[20px] font-semibold">Ask SPI to handle payroll work</h3>
              <p className="mt-1.5 max-w-md text-[13.5px] leading-6 text-ink-2">
                SPI looks things up and prepares changes for you — salaries, staff IDs, payroll runs, funding links. Anything that changes data waits for your confirmation; paying staff also needs your password.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" onClick={() => send.mutate(s)} className="rounded-full border border-line bg-raised px-3.5 py-2 text-left text-[13px] text-ink-2 transition hover:border-brand hover:text-ink">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid gap-4">
            {timeline.map((row) =>
              row.kind === "msg" ? (
                <div key={row.m.id} className={cx("flex", row.m.role === "user" ? "justify-end" : "justify-start")}>
                  <div
                    className={cx(
                      "max-w-[88%] rounded-2xl px-4 py-2.5 text-[14px] leading-6",
                      row.m.role === "user" ? "rounded-br-md bg-ink text-shell" : "rounded-bl-md border border-line bg-raised text-ink",
                    )}
                  >
                    {row.m.role === "user" ? row.m.text : <RichText text={row.m.text} />}
                  </div>
                </div>
              ) : (
                <Fragment key={row.a.id}>
                  <ActionCard
                    action={row.a}
                    onResolved={(_, message) => {
                      queryClient.invalidateQueries({ queryKey: key });
                      refreshAppData();
                      toast.success(message);
                    }}
                  />
                </Fragment>
              ),
            )}
            {send.isPending && (
              <div className="flex items-center gap-2 text-[13px] text-ink-3">
                <Spinner size={14} /> SPI is working…
              </div>
            )}
          </div>
        )}
      </div>
      <form onSubmit={submit} className={cx("border-t border-line bg-surface", compact ? "p-3" : "p-4")}>
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-raised p-1.5 pl-4 focus-within:border-brand focus-within:shadow-[0_0_0_4px_var(--c-glow)]">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={1}
            maxLength={2000}
            placeholder={workgroupId ? "Ask or tell SPI what to do…" : "Create a workgroup to let SPI act on it"}
            aria-label="Message SPI"
            className="max-h-36 min-h-9 flex-1 resize-none bg-transparent py-2 text-[14px] outline-none placeholder:text-ink-3"
          />
          <Button type="submit" size="sm" className="h-9 w-9 !px-0" disabled={!input.trim()} loading={send.isPending} aria-label="Send">
            {!send.isPending && <ArrowUp size={16} />}
          </Button>
        </div>
        <div className="mt-2 flex items-center justify-between px-1 text-[11.5px] text-ink-3">
          <span>{conversation.data?.mode === "basic" ? "Basic mode — direct commands" : "SPI can make mistakes; check amounts before confirming"}</span>
          {quota && (
            <span className="num">
              {quota.remaining.toLocaleString()} of {quota.limit.toLocaleString()} left this month
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
