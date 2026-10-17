import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Download, FileSpreadsheet, Plus, Search, UserPlus, X } from "lucide-react";
import {
  Avatar,
  Badge,
  Button,
  ButtonLink,
  Card,
  cx,
  Drawer,
  EmptyState,
  ErrorState,
  Input,
  KeyValue,
  Menu,
  MenuItem,
  Modal,
  MoneyInput,
  Notice,
  PageHeader,
  Pagination,
  Segmented,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
} from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup } from "../../context/workgroup";
import { ApiError, api } from "../../lib/api";
import { date, dateTime, naira, plural } from "../../lib/format";
import { useBanks, wgKey } from "../../lib/queries";
import type { Paged, Role, Staff } from "../../lib/types";

type Filter = "all" | "registered" | "pending" | "inactive";

function BankFields({ bank, account, onBank, onAccount }: { bank: string; account: string; onBank: (v: string) => void; onAccount: (v: string) => void }) {
  const banks = useBanks();
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Select label="Bank" value={bank} onChange={(e) => onBank(e.target.value)}>
        <option value="">Choose bank</option>
        {(banks.data ?? []).map((b) => (
          <option key={b.code} value={b.code}>
            {b.name}
          </option>
        ))}
      </Select>
      <Input label="Account number" inputMode="numeric" maxLength={10} placeholder="10 digits" className="num" value={account} onChange={(e) => onAccount(e.target.value.replace(/\D/g, "").slice(0, 10))} />
    </div>
  );
}

function StaffDrawer({ staffId, onClose, roles }: { staffId: string; onClose: () => void; roles: Role[] }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const detail = useQuery({ queryKey: wgKey(workgroup.id, "staff-detail", staffId), queryFn: () => api.get<Staff>(`/workgroups/${workgroup.id}/staff/${staffId}`) });
  const m = detail.data;
  const [roleId, setRoleId] = useState("");
  const [override, setOverride] = useState<number | null>(null);
  const [useOverride, setUseOverride] = useState(false);
  const [bankOpen, setBankOpen] = useState(false);
  const [bank, setBank] = useState("");
  const [account, setAccount] = useState("");
  const [confirm, setConfirm] = useState<null | "reset" | "deactivate" | "delete">(null);

  useEffect(() => {
    if (!m) return;
    setRoleId(m.role_id ?? "");
    setOverride(m.salary_override_kobo);
    setUseOverride(m.salary_override_kobo !== null || !m.role_id);
  }, [m]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api.patch<Staff>(`/workgroups/${workgroup.id}/staff/${staffId}`, body),
    onSuccess: () => {
      toast.success("Saved");
      invalidate();
    },
    onError: (e) => toast.error(e),
  });
  const changeBank = useMutation({
    mutationFn: () => api.post<Staff>(`/workgroups/${workgroup.id}/staff/${staffId}/bank`, { bank_code: bank, account_number: account }),
    onSuccess: (s) => {
      toast.success("Bank account verified", `${s.account_name} · ${s.bank_name}`);
      setBankOpen(false);
      setAccount("");
      invalidate();
    },
  });
  const act = useMutation({
    mutationFn: async (kind: "reset" | "deactivate" | "reactivate" | "delete") => {
      if (kind === "reset") return api.post(`/workgroups/${workgroup.id}/staff/${staffId}/reset`);
      if (kind === "delete") return api.delete(`/workgroups/${workgroup.id}/staff/${staffId}`);
      return api.patch(`/workgroups/${workgroup.id}/staff/${staffId}`, { status: kind === "deactivate" ? "inactive" : "active" });
    },
    onSuccess: (_, kind) => {
      toast.success({ reset: "Registration reset", deactivate: "Staff member deactivated", reactivate: "Staff member reactivated", delete: "Staff ID deleted" }[kind]);
      setConfirm(null);
      invalidate();
      if (kind === "delete") onClose();
    },
    onError: (e) => toast.error(e),
  });

  const role = roles.find((r) => r.id === roleId);
  const effective = useOverride ? override ?? 0 : role?.salary_kobo ?? 0;

  function savePay(e: FormEvent) {
    e.preventDefault();
    save.mutate({ role_id: roleId || null, salary_kobo: useOverride ? override ?? 0 : null });
  }

  return (
    <Drawer
      open
      onClose={onClose}
      title={m ? m.name || "Unclaimed staff ID" : "Loading…"}
      subtitle={m && (
        <span className="flex items-center gap-2">
          <span className="num font-semibold tracking-wide text-ink-2">{m.staff_code}</span>
          <StatusPill status={m.status} />
        </span>
      )}
    >
      {!m ? (
        <div className="grid gap-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-40" />
        </div>
      ) : (
        <div className="grid gap-7">
          {m.status === "registered" && m.name_match === false && (
            <Notice tone="warn" title="Bank name doesn't match">
              The bank says this account belongs to <strong>{m.account_name}</strong>, but the staff member registered as <strong>{m.name}</strong>. Confirm with them before paying.
            </Notice>
          )}

          <section>
            <h3 className="mb-3 text-[13px] font-semibold text-ink-3">Pay</h3>
            <form onSubmit={savePay} className="grid gap-4">
              <Select label="Role" value={roleId} onChange={(e) => { setRoleId(e.target.value); if (!e.target.value) setUseOverride(true); }}>
                <option value="">No role</option>
                {roles.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} — {naira(r.salary_kobo)}
                  </option>
                ))}
              </Select>
              {roleId && (
                <label className="flex items-center gap-2 text-[13px] text-ink-2">
                  <input type="checkbox" className="h-4 w-4 accent-[var(--c-brand)]" checked={useOverride} onChange={(e) => setUseOverride(e.target.checked)} />
                  Give this person a different salary from the role
                </label>
              )}
              {useOverride && <MoneyInput label="Monthly salary" valueKobo={override} onChangeKobo={setOverride} />}
              <div className="flex items-center justify-between rounded-xl bg-soft/60 px-4 py-3 text-[13.5px]">
                <span className="text-ink-2">Paid each payday</span>
                <span className="num font-semibold">{naira(effective)}</span>
              </div>
              <div>
                <Button type="submit" loading={save.isPending}>
                  Save pay
                </Button>
              </div>
            </form>
          </section>

          {m.status !== "pending" && (
            <section>
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-[13px] font-semibold text-ink-3">Bank account</h3>
                {!bankOpen && (
                  <button type="button" onClick={() => { setBankOpen(true); setBank(m.bank_code ?? ""); }} className="text-[12.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
                    Change
                  </button>
                )}
              </div>
              {bankOpen ? (
                <div className="grid gap-4 rounded-2xl border border-line p-4">
                  <BankFields bank={bank} account={account} onBank={setBank} onAccount={setAccount} />
                  {changeBank.error && <Notice tone="bad">{(changeBank.error as ApiError).message}</Notice>}
                  <div className="flex gap-2">
                    <Button size="sm" loading={changeBank.isPending} disabled={!bank || account.length !== 10} onClick={() => changeBank.mutate()}>
                      Verify and save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setBankOpen(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <KeyValue
                  rows={[
                    ["Account name", <span className="inline-flex items-center gap-1.5">{m.account_name ?? "—"}{m.bank_verified && <BadgeCheck size={15} className="text-good" aria-label="Verified" />}</span>],
                    ["Bank", m.bank_name ?? "—"],
                    ["Account number", <span className="num">{m.account_number ?? "—"}</span>],
                  ]}
                />
              )}
            </section>
          )}

          <section>
            <h3 className="mb-3 text-[13px] font-semibold text-ink-3">Details</h3>
            <KeyValue
              rows={[
                ["Email", m.email ?? "—"],
                ["Phone", m.phone ?? "—"],
                ["Name on your list", m.preset_name ?? "—"],
                ["Registered", m.registered_at ? dateTime(m.registered_at) : "Not yet"],
                ["ID source", <span className="capitalize">{m.source}</span>],
              ]}
            />
          </section>

          {m.payments && m.payments.length > 0 && (
            <section>
              <h3 className="mb-3 text-[13px] font-semibold text-ink-3">Payment history</h3>
              <ul className="divide-y divide-line rounded-2xl border border-line">
                {m.payments.map((p) => (
                  <li key={p.id}>
                    <Link to={`/app/payroll/runs/${p.run_id}`} className="flex items-center justify-between gap-3 px-4 py-3 text-[13.5px] hover:bg-soft/40">
                      <span>
                        <span className="block font-medium">{p.period}</span>
                        <span className="block text-[12px] text-ink-3">{p.paid_at ? date(p.paid_at) : p.failure_reason ?? p.run_number}</span>
                      </span>
                      <span className="text-right">
                        <span className="num block font-semibold">{naira(p.amount_kobo)}</span>
                        <StatusPill status={p.status} />
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="grid gap-2 border-t border-line pt-5">
            {m.status === "registered" && (
              <Button variant="secondary" onClick={() => setConfirm("reset")}>
                Reset registration
              </Button>
            )}
            {m.status === "inactive" ? (
              <Button variant="secondary" loading={act.isPending} onClick={() => act.mutate("reactivate")}>
                Reactivate
              </Button>
            ) : m.status === "registered" ? (
              <Button variant="ghost" className="text-bad" onClick={() => setConfirm("deactivate")}>
                Deactivate
              </Button>
            ) : (
              <Button variant="ghost" className="text-bad" onClick={() => setConfirm("delete")}>
                Delete staff ID
              </Button>
            )}
          </section>
        </div>
      )}
      <Modal
        open={confirm !== null}
        onClose={() => setConfirm(null)}
        size="sm"
        title={confirm === "reset" ? "Reset this registration?" : confirm === "deactivate" ? "Deactivate this staff member?" : "Delete this staff ID?"}
        description={
          confirm === "reset"
            ? "Their name and bank details are cleared and the staff ID becomes claimable again, so they can fill the form afresh."
            : confirm === "deactivate"
              ? "They won't be included in payroll. Their payment history is kept and you can reactivate them later."
              : "The ID is removed and its seat is freed."
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button>
            <Button variant={confirm === "reset" ? "dark" : "danger"} loading={act.isPending} onClick={() => confirm && act.mutate(confirm)}>
              {confirm === "reset" ? "Reset registration" : confirm === "deactivate" ? "Deactivate" : "Delete"}
            </Button>
          </>
        }
      />
    </Drawer>
  );
}

function AddStaffModal({ open, onClose, roles }: { open: boolean; onClose: () => void; roles: Role[] }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState({ staff_code: "", first_name: "", last_name: "", email: "", phone: "", role_id: "" });
  const [salary, setSalary] = useState<number | null>(null);
  const [bank, setBank] = useState("");
  const [account, setAccount] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api.post<Staff>(`/workgroups/${workgroup.id}/staff`, {
        ...form,
        staff_code: form.staff_code || null,
        email: form.email || null,
        phone: form.phone || null,
        role_id: form.role_id || null,
        salary_kobo: salary,
        bank_code: bank,
        account_number: account,
      }),
    onSuccess: (s) => {
      toast.success(`${s.name} added`, `Verified: ${s.account_name}`);
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      onClose();
    },
  });
  const err = mutation.error as ApiError | null;
  const f = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add a staff member"
      description="For someone who can't use the onboarding link. Their bank account is verified before saving."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} disabled={!form.first_name || !form.last_name || !bank || account.length !== 10} onClick={() => mutation.mutate()}>
            Verify and add
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        {err && <Notice tone={err.code === "seats_exceeded" ? "warn" : "bad"}>{err.message}</Notice>}
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="First name" value={form.first_name} onChange={f("first_name")} />
          <Input label="Last name" value={form.last_name} onChange={f("last_name")} />
        </div>
        <Input label="Staff ID" optional placeholder={`Leave blank to generate (${workgroup.staff_id_prefix}-XXXX-XXXX)`} value={form.staff_code} onChange={f("staff_code")} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Email" type="email" optional hint="For payslips" value={form.email} onChange={f("email")} />
          <Input label="Phone" type="tel" optional value={form.phone} onChange={f("phone")} />
        </div>
        <BankFields bank={bank} account={account} onBank={setBank} onAccount={setAccount} />
        <div className="grid gap-4 sm:grid-cols-2">
          <Select label="Role" value={form.role_id} onChange={f("role_id")}>
            <option value="">No role</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.name}</option>
            ))}
          </Select>
          <MoneyInput label="Monthly salary" optional={Boolean(form.role_id)} hint={form.role_id ? "Leave blank to use the role's salary" : undefined} valueKobo={salary} onChangeKobo={setSalary} />
        </div>
      </div>
    </Modal>
  );
}

function BulkBar({ ids, roles, onDone }: { ids: string[]; roles: Role[]; onDone: () => void }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const [mode, setMode] = useState<"role" | "salary">("role");
  const [roleId, setRoleId] = useState("");
  const [salary, setSalary] = useState<number | null>(null);
  const mutation = useMutation({
    mutationFn: () => api.post<{ updated: number }>(`/workgroups/${workgroup.id}/staff/bulk`, mode === "role" ? { staff_ids: ids, role_id: roleId || null } : { staff_ids: ids, salary_kobo: salary }),
    onSuccess: (r) => {
      toast.success(`Updated ${plural(r.updated, "staff member")}`);
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      onDone();
    },
    onError: (e) => toast.error(e),
  });
  return (
    <div className="flex flex-wrap items-end gap-3 border-b border-line bg-brand-soft/50 px-4 py-3">
      <p className="mb-2.5 text-[13px] font-semibold">{ids.length.toLocaleString("en-NG")} selected</p>
      <Segmented size="sm" className="mb-1" value={mode} onChange={setMode} options={[{ value: "role", label: "Set role" }, { value: "salary", label: "Set salary" }]} />
      {mode === "role" ? (
        <div className="w-56">
          <Select aria-label="Role" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">No role</option>
            {roles.map((r) => (
              <option key={r.id} value={r.id}>{r.name} — {naira(r.salary_kobo)}</option>
            ))}
          </Select>
        </div>
      ) : (
        <div className="w-48">
          <MoneyInput valueKobo={salary} onChangeKobo={setSalary} />
        </div>
      )}
      <Button size="md" loading={mutation.isPending} disabled={mode === "salary" && salary === null} onClick={() => mutation.mutate()}>
        Apply
      </Button>
      <Button size="md" variant="ghost" icon={<X size={15} />} onClick={onDone}>
        Clear
      </Button>
    </div>
  );
}

export default function StaffPage() {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const filter = (params.get("status") as Filter) || "all";
  const attention = params.get("attention") === "1";
  const [q, setQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(params.get("focus"));
  const [adding, setAdding] = useState(false);

  const roles = useQuery({ queryKey: wgKey(workgroup.id, "roles"), queryFn: () => api.get<Role[]>(`/workgroups/${workgroup.id}/roles`) });
  const list = useQuery({
    queryKey: wgKey(workgroup.id, "staff", filter, q, roleFilter, attention, page),
    queryFn: () =>
      api.get<Paged<Staff>>(`/workgroups/${workgroup.id}/staff`, {
        status: filter === "all" ? undefined : filter,
        q: q || undefined,
        role_id: roleFilter || undefined,
        attention: attention || undefined,
        page,
        page_size: 50,
      }),
    placeholderData: keepPreviousData,
  });
  const items = useMemo(() => list.data?.items ?? [], [list.data]);
  const allSelected = items.length > 0 && items.every((m) => selected.has(m.id));

  function setFilter(next: Partial<{ status: Filter; attention: boolean }>) {
    const status = next.status ?? filter;
    const att = next.attention ?? attention;
    const p: Record<string, string> = {};
    if (status !== "all") p.status = status;
    if (att) p.attention = "1";
    setParams(p);
    setPage(1);
    setSelected(new Set());
  }

  return (
    <div>
      <PageHeader
        title="Staff"
        description="Everyone in this workgroup, their pay and the bank account they registered."
        action={
          <>
            <Menu trigger={({ toggle }) => <Button variant="secondary" icon={<Download size={16} />} onClick={toggle}>Export</Button>}>
              {(close) => (
                <>
                  <MenuItem icon={<FileSpreadsheet size={16} />} onClick={() => { close(); void api.download(`/workgroups/${workgroup.id}/staff/export`, "staff.xlsx", { format: "xlsx" }).catch(toast.error); }}>Excel (.xlsx)</MenuItem>
                  <MenuItem icon={<Download size={16} />} onClick={() => { close(); void api.download(`/workgroups/${workgroup.id}/staff/export`, "staff.csv").catch(toast.error); }}>CSV</MenuItem>
                </>
              )}
            </Menu>
            <ButtonLink to="/app/onboarding" variant="secondary" icon={<UserPlus size={16} />}>
              Invite staff
            </ButtonLink>
            <Button icon={<Plus size={16} />} onClick={() => setAdding(true)}>
              Add manually
            </Button>
          </>
        }
      />

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <Segmented<Filter>
              value={filter}
              onChange={(v) => setFilter({ status: v })}
              options={[
                { value: "all", label: "All" },
                { value: "registered", label: "Registered" },
                { value: "pending", label: "Unclaimed" },
                { value: "inactive", label: "Inactive" },
              ]}
            />
            <button
              type="button"
              onClick={() => setFilter({ attention: !attention })}
              aria-pressed={attention}
              className={cx("inline-flex h-10 items-center gap-1.5 rounded-xl border px-3 text-[13px] font-medium transition", attention ? "border-warn/40 bg-warn-soft text-warn" : "border-line text-ink-2 hover:border-line-strong")}
            >
              <AlertTriangle size={14} /> Needs attention
            </button>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="sm:w-48">
              <Select aria-label="Filter by role" value={roleFilter} onChange={(e) => { setRoleFilter(e.target.value); setPage(1); }}>
                <option value="">All roles</option>
                {(roles.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </Select>
            </div>
            <div className="sm:w-72">
              <Input leading={<Search size={15} />} placeholder="Name, staff ID, email or account" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} aria-label="Search staff" />
            </div>
          </div>
        </div>

        {selected.size > 0 && <BulkBar ids={[...selected]} roles={roles.data ?? []} onDone={() => setSelected(new Set())} />}

        {list.error ? (
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        ) : list.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : items.length === 0 ? (
          <EmptyState
            icon={<UserPlus size={20} />}
            title={q || filter !== "all" || attention || roleFilter ? "Nobody matches" : "No staff yet"}
            action={!q && filter === "all" && !attention && <ButtonLink to="/app/onboarding">Share the onboarding link</ButtonLink>}
          >
            {q || filter !== "all" || attention || roleFilter ? "Try another filter or search term." : "Staff appear here as they register with their staff IDs."}
          </EmptyState>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th className="w-10 pr-0">
                    <input
                      type="checkbox"
                      aria-label="Select all on this page"
                      className="h-4 w-4 accent-[var(--c-brand)]"
                      checked={allSelected}
                      onChange={(e) => setSelected(e.target.checked ? new Set(items.map((m) => m.id)) : new Set())}
                    />
                  </Th>
                  <Th>Staff</Th>
                  <Th>Role</Th>
                  <Th align="right">Monthly pay</Th>
                  <Th>Bank account</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {items.map((m) => (
                  <tr key={m.id} className="cursor-pointer transition hover:bg-soft/40" onClick={() => setOpen(m.id)}>
                    <Td className="w-10 pr-0">
                      <input
                        type="checkbox"
                        aria-label={`Select ${m.name || m.staff_code}`}
                        className="h-4 w-4 accent-[var(--c-brand)]"
                        checked={selected.has(m.id)}
                        onClick={(e) => e.stopPropagation()}
                        onChange={(e) => {
                          const next = new Set(selected);
                          if (e.target.checked) next.add(m.id);
                          else next.delete(m.id);
                          setSelected(next);
                        }}
                      />
                    </Td>
                    <Td>
                      <div className="flex items-center gap-3">
                        <Avatar name={m.name || m.staff_code} size={34} />
                        <div className="min-w-0">
                          <p className="truncate font-medium">{m.name || <span className="text-ink-3">Not registered</span>}</p>
                          <p className="num text-[12px] tracking-wide text-ink-3">{m.staff_code}</p>
                        </div>
                      </div>
                    </Td>
                    <Td className="text-ink-2">{m.role_name ?? "—"}</Td>
                    <Td align="right" className={m.salary_kobo ? "font-medium" : "text-warn"}>
                      {m.salary_kobo ? naira(m.salary_kobo) : m.status === "registered" ? "Not set" : "—"}
                    </Td>
                    <Td>
                      {m.bank_name ? (
                        <div className="flex items-center gap-2">
                          <span className="text-ink-2">
                            {m.bank_name} <span className="num">{m.account_number}</span>
                          </span>
                          {m.name_match === false ? <Badge tone="warn">Name differs</Badge> : m.bank_verified && <BadgeCheck size={15} className="text-good" aria-label="Verified" />}
                        </div>
                      ) : (
                        <span className="text-ink-3">—</span>
                      )}
                    </Td>
                    <Td>
                      <StatusPill status={m.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pagination page={page} pageSize={50} total={list.data?.total ?? 0} onPage={setPage} />
          </>
        )}
      </Card>

      {open && (
        <StaffDrawer
          staffId={open}
          roles={roles.data ?? []}
          onClose={() => {
            setOpen(null);
            if (params.get("focus")) {
              params.delete("focus");
              setParams(params);
            }
          }}
        />
      )}
      {adding && <AddStaffModal open onClose={() => setAdding(false)} roles={roles.data ?? []} />}
    </div>
  );
}
