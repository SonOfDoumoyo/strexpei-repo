import { type FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { QrCard } from "../../components/QrCard";
import { Button, ButtonLink, Card, CardHeader, CopyButton, Modal, Notice, PageHeader, Progress, Textarea, Toggle } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { plural, relative } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { AuditEntry, IdsSummary, Paged, Workgroup } from "../../lib/types";

export default function Onboarding() {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const [rotateOpen, setRotateOpen] = useState(false);
  const [emails, setEmails] = useState("");
  const [message, setMessage] = useState("");

  const summary = useQuery({ queryKey: wgKey(workgroup.id, "ids-summary"), queryFn: () => api.get<IdsSummary>(`/workgroups/${workgroup.id}/staff-ids/summary`) });
  const registered = useQuery({
    queryKey: wgKey(workgroup.id, "registrations"),
    queryFn: () => api.get<Paged<AuditEntry>>(`/workgroups/${workgroup.id}/activity`, { action: "staff.registered", page_size: 8 }),
    refetchInterval: 30_000,
  });
  const regCount = useQuery({
    queryKey: wgKey(workgroup.id, "staff", "registered-count"),
    queryFn: () => api.get<Paged<unknown>>(`/workgroups/${workgroup.id}/staff`, { status: "registered", page_size: 1 }),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["workgroups"] });
    qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
  };
  const toggle = useMutation({
    mutationFn: (active: boolean) => api.post<Workgroup>(`/workgroups/${workgroup.id}/invite/toggle`, { active }),
    onSuccess: (wg) => {
      toast.success(wg.invite_active ? "Registrations are open" : "Registrations paused");
      refresh();
    },
    onError: (e) => toast.error(e),
  });
  const rotate = useMutation({
    mutationFn: () => api.post<Workgroup>(`/workgroups/${workgroup.id}/invite/rotate`),
    onSuccess: () => {
      toast.success("New link created", "The old link and QR code no longer work.");
      setRotateOpen(false);
      refresh();
    },
    onError: (e) => toast.error(e),
  });
  const parsedEmails = emails.split(/[\s,;]+/).map((e) => e.trim()).filter(Boolean);
  const invite = useMutation({
    mutationFn: () => api.post<{ sent: number }>(`/workgroups/${workgroup.id}/invite/email`, { emails: parsedEmails, message: message.trim() || null }),
    onSuccess: (r) => {
      toast.success(`Invitation sent to ${plural(r.sent, "person", "people")}`);
      setEmails("");
      setMessage("");
    },
    onError: (e) => toast.error(e),
  });

  const total = summary.data?.headcount ?? workgroup.headcount;
  const done = regCount.data?.total ?? 0;
  const noIds = summary.data && summary.data.in_use === 0;

  return (
    <div>
      <PageHeader title="Onboarding link" description="Share one link or QR code. Staff register themselves with their staff ID — no app, no account." />

      {noIds && (
        <Notice tone="warn" className="mb-6" title="Add staff IDs first" action={<ButtonLink to="/app/staff-ids" size="sm" variant="dark">Set up staff IDs</ButtonLink>}>
          Staff can only register with an ID from your list. Without IDs, nobody can complete the form.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Card className="p-6 sm:p-8">
          <QrCard workgroup={workgroup} size={220} />
          <div className="mt-6 flex items-center gap-2 rounded-2xl border border-line bg-raised p-2 pl-4">
            <span className="num min-w-0 flex-1 truncate text-[13px] font-medium">{workgroup.join_url}</span>
            <CopyButton text={workgroup.join_url} label="Copy" variant="soft" />
          </div>
          <div className="mt-6 grid gap-5 border-t border-line pt-6">
            <Toggle
              checked={workgroup.invite_active}
              disabled={toggle.isPending}
              onChange={(v) => toggle.mutate(v)}
              label="Accept registrations"
              description={workgroup.invite_active ? "Anyone with a valid staff ID can register." : "The form is closed. Staff see a message to contact you."}
            />
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[14px] font-medium">Replace link and QR code</p>
                <p className="mt-0.5 text-[12.5px] leading-5 text-ink-3">Use this if the link was shared somewhere it shouldn't be.</p>
              </div>
              <Button size="sm" variant="secondary" icon={<RefreshCw size={14} />} onClick={() => setRotateOpen(true)}>
                Replace
              </Button>
            </div>
          </div>
        </Card>

        <div className="grid content-start gap-6">
          <Card className="p-6">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-[16px] font-semibold">Registrations</h2>
              <p className="num text-[13px] text-ink-3">
                {done} of {total}
              </p>
            </div>
            <Progress value={done} max={Math.max(1, total)} className="mt-3" tone={done >= total && total > 0 ? "good" : "brand"} label="Registered staff" />
            <ul className="mt-5 divide-y divide-line">
              {(registered.data?.items ?? []).map((a) => (
                <li key={a.id} className="flex items-center justify-between gap-3 py-2.5 text-[13.5px]">
                  <span className="min-w-0 truncate">{a.summary.replace(" registered with staff ID", " ·")}</span>
                  <span className="shrink-0 text-[12px] text-ink-3">{relative(a.created_at)}</span>
                </li>
              ))}
              {registered.data && registered.data.items.length === 0 && <li className="py-3 text-[13px] text-ink-3">Nobody has registered yet. New registrations appear here.</li>}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Email the link" description="We send each person a short invitation with the link." />
            <form
              className="grid gap-4 p-5 sm:p-6"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                invite.mutate();
              }}
            >
              <Textarea label="Email addresses" placeholder={"chidi@example.com, amaka@example.com"} hint="Separate with commas or new lines. Up to 200 at a time." value={emails} onChange={(e) => setEmails(e.target.value)} className="min-h-24" />
              <Textarea label="Note from you" placeholder="Please register before Friday so you're paid on time." value={message} maxLength={300} onChange={(e) => setMessage(e.target.value)} className="min-h-20" />
              <div>
                <Button type="submit" loading={invite.isPending} disabled={!parsedEmails.length || parsedEmails.length > 200}>
                  Send to {parsedEmails.length ? plural(parsedEmails.length, "person", "people") : "staff"}
                </Button>
              </div>
            </form>
          </Card>

          <Card className="p-6">
            <h2 className="text-[16px] font-semibold">What your staff will do</h2>
            <ol className="mt-4 grid gap-3 text-[13.5px] leading-6 text-ink-2">
              <li><span className="mr-2 font-semibold text-ink">1.</span>Open the link or scan the QR code on their phone.</li>
              <li><span className="mr-2 font-semibold text-ink">2.</span>Enter the staff ID you gave them. Unknown or already-used IDs are rejected.</li>
              <li><span className="mr-2 font-semibold text-ink">3.</span>Add their name, email and bank account. We confirm the account name with the bank instantly.</li>
              <li><span className="mr-2 font-semibold text-ink">4.</span>Tap done. They get a confirmation email, and you get a notification.</li>
            </ol>
          </Card>
        </div>
      </div>

      <Modal
        open={rotateOpen}
        onClose={() => setRotateOpen(false)}
        size="sm"
        title="Replace the onboarding link?"
        description="The current link and any printed QR codes stop working immediately. Staff who already registered aren't affected."
        footer={
          <>
            <Button variant="ghost" onClick={() => setRotateOpen(false)}>Cancel</Button>
            <Button variant="dark" loading={rotate.isPending} onClick={() => rotate.mutate()}>Replace link</Button>
          </>
        }
      />
    </div>
  );
}
