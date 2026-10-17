import { type FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Lock, Moon, Sun } from "lucide-react";
import { PasswordModal } from "../../components/PasswordModal";
import { Button, ButtonLink, Card, CardHeader, cx, Input, Notice, PageHeader, Segmented, Select } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useAuth } from "../../context/auth";
import { ACCENTS, useTheme } from "../../context/theme";
import { useWorkgroups } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import type { User, Workgroup } from "../../lib/types";

type Tab = "profile" | "security" | "appearance" | "workgroup";

function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ first_name: user?.first_name ?? "", last_name: user?.last_name ?? "", phone: user?.phone ?? "" });
  const save = useMutation({
    mutationFn: () => api.patch<User>("/users/me", { ...form, phone: form.phone || null }),
    onSuccess: (u) => {
      setUser(u);
      toast.success("Profile saved");
    },
    onError: (e) => toast.error(e),
  });
  return (
    <Card>
      <CardHeader title="Your details" description="Shown to staff on the onboarding form and in emails." />
      <form className="grid gap-5 p-5 sm:p-6" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
        <div className="grid gap-5 sm:grid-cols-2">
          <Input label="First name" value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          <Input label="Last name" value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
        </div>
        <Input label="Email" value={user?.email ?? ""} disabled hint="Contact support to change the email on your account." />
        <Input label="Phone" type="tel" optional value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <div><Button type="submit" loading={save.isPending}>Save details</Button></div>
      </form>
    </Card>
  );
}

function Security() {
  const toast = useToast();
  const { logout } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const change = useMutation({
    mutationFn: () => api.post<{ message: string }>("/users/me/password", { current_password: current, new_password: next }),
    onSuccess: async () => {
      toast.success("Password changed", "Please sign in again.");
      await logout();
    },
  });
  const err = change.error as ApiError | null;
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader title="Change password" description="You'll be signed out everywhere, including this device." />
        <form className="grid gap-5 p-5 sm:p-6" onSubmit={(e: FormEvent) => { e.preventDefault(); change.mutate(); }}>
          {err && <Notice tone="bad">{err.details?.fields?.new_password ?? err.message}</Notice>}
          <Input label="Current password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          <Input label="New password" type="password" autoComplete="new-password" hint="At least 8 characters with a letter and a number." value={next} onChange={(e) => setNext(e.target.value)} />
          <div><Button type="submit" variant="dark" loading={change.isPending} disabled={!current || next.length < 8}>Change password</Button></div>
        </form>
      </Card>
      <Card className="border-bad/25">
        <CardHeader title="Delete account" description="Your account is closed now and permanently removed after 30 days. Sign in within 30 days to restore it." />
        <div className="grid gap-4 p-5 sm:p-6">
          <p className="text-[13px] leading-6 text-ink-2">First withdraw any money left in your workgroup wallets — open Wallet and choose Withdraw. Payroll records are kept for your staff's tax and audit needs.</p>
          <div><Button variant="danger" onClick={() => setDeleteOpen(true)}>Delete my account</Button></div>
        </div>
      </Card>
      <PasswordModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        danger
        title="Delete your account?"
        description="All your workgroups are closed and onboarding links stop working."
        confirmLabel="Delete account"
        onConfirm={async (password) => {
          await api.post("/users/me/delete", { password });
          toast.success("Account scheduled for deletion");
          await logout();
        }}
      />
    </div>
  );
}

function Appearance() {
  const { mode, setMode, accent, setAccent, canCustomize } = useTheme();
  return (
    <Card>
      <CardHeader title="Appearance" />
      <div className="grid gap-7 p-5 sm:p-6">
        <div className="grid gap-2">
          <span className="text-[13px] font-medium">Mode</span>
          <Segmented
            value={mode}
            onChange={setMode}
            options={[
              { value: "light", label: <span className="inline-flex items-center gap-1.5"><Sun size={14} /> Light</span> },
              { value: "dark", label: <span className="inline-flex items-center gap-1.5"><Moon size={14} /> Dark</span> },
            ]}
          />
        </div>
        <div className="grid gap-3">
          <div>
            <span className="text-[13px] font-medium">Accent</span>
            <p className="text-[12.5px] text-ink-3">{canCustomize ? "Pick the accent for your workspace." : "Gold, Diamond and Premium accents unlock with any paid plan."}</p>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {ACCENTS.map((a) => {
              const locked = a.locked && !canCustomize;
              const active = accent.id === a.id;
              return (
                <button
                  key={a.id}
                  type="button"
                  disabled={locked}
                  onClick={() => setAccent(a.id)}
                  aria-pressed={active}
                  className={cx("relative rounded-2xl border p-3 text-left transition disabled:cursor-not-allowed", active ? "border-ink ring-4 ring-glow" : "border-line hover:border-line-strong", locked && "opacity-55")}
                >
                  <span className="flex gap-1.5">
                    <span className="h-7 w-7 rounded-lg" style={{ background: mode === "dark" ? a.dark : a.light }} />
                    <span className="h-7 w-7 rounded-lg border border-line" style={{ background: a.soft }} />
                  </span>
                  <span className="mt-2.5 flex items-center justify-between text-[13px] font-semibold">
                    {a.name}
                    {locked ? <Lock size={13} className="text-ink-3" /> : active ? <Check size={14} /> : null}
                  </span>
                </button>
              );
            })}
          </div>
          {!canCustomize && <div><ButtonLink to="/app/billing" size="sm" variant="secondary">See plans</ButtonLink></div>}
        </div>
      </div>
    </Card>
  );
}

function WorkgroupSettings() {
  const { workgroup, refresh } = useWorkgroups();
  const toast = useToast();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", address: "", industry: "" });
  const [archiveOpen, setArchiveOpen] = useState(false);
  useEffect(() => {
    if (workgroup) setForm({ name: workgroup.name, address: workgroup.address ?? "", industry: workgroup.industry ?? "" });
  }, [workgroup]);
  const save = useMutation({
    mutationFn: () => api.patch<Workgroup>(`/workgroups/${workgroup!.id}`, { name: form.name, address: form.address || null, industry: form.industry || null }),
    onSuccess: async () => {
      await refresh();
      toast.success("Workgroup saved");
    },
    onError: (e) => toast.error(e),
  });
  if (!workgroup) return <Notice tone="info">Create a workgroup first.</Notice>;
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader title={workgroup.name} description="Staff see this name on the onboarding form, emails and payslips." />
        <form className="grid gap-5 p-5 sm:p-6" onSubmit={(e: FormEvent) => { e.preventDefault(); save.mutate(); }}>
          <Input label="Name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input label="Address" optional value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          <Select label="Industry" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
            <option value="">Not set</option>
            {["Retail", "Logistics & transport", "Hospitality", "Healthcare", "Education", "Manufacturing", "Construction", "Agriculture", "Technology", "Professional services", "Security", "Church / NGO", "Other"].map((i) => <option key={i}>{i}</option>)}
          </Select>
          <div><Button type="submit" loading={save.isPending} disabled={form.name.trim().length < 2}>Save workgroup</Button></div>
        </form>
      </Card>
      <Card className="border-bad/25">
        <CardHeader title="Delete this workgroup" description="Its onboarding link stops working and it's removed from your list. Withdraw any wallet balance first." />
        <div className="p-5 sm:p-6"><Button variant="danger" onClick={() => setArchiveOpen(true)}>Delete {workgroup.name}</Button></div>
      </Card>
      <PasswordModal
        open={archiveOpen}
        onClose={() => setArchiveOpen(false)}
        danger
        title={`Delete ${workgroup.name}?`}
        description="Staff records and payroll history are kept for audit, but you won't be able to run payroll for this workgroup again."
        confirmLabel="Delete workgroup"
        onConfirm={async (password) => {
          await api.post(`/workgroups/${workgroup.id}/archive`, { password });
          toast.success(`${workgroup.name} deleted`);
          await refresh();
          qc.clear();
          setArchiveOpen(false);
          navigate("/app");
        }}
      />
    </div>
  );
}

export default function Settings() {
  const [tab, setTab] = useState<Tab>("profile");
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" />
      <div className="mb-6 overflow-x-auto">
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { value: "profile", label: "Profile" },
            { value: "security", label: "Security" },
            { value: "appearance", label: "Appearance" },
            { value: "workgroup", label: "Workgroup" },
          ]}
        />
      </div>
      {tab === "profile" && <Profile />}
      {tab === "security" && <Security />}
      {tab === "appearance" && <Appearance />}
      {tab === "workgroup" && <WorkgroupSettings />}
    </div>
  );
}
