import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, ShieldCheck, Trash2 } from "lucide-react";
import { Button, Card, CardHeader, EmptyState, ErrorState, IconButton, Input, Modal, MoneyInput, PageHeader, Skeleton, Table, Td, Th } from "../../components/ui";
import { useToast } from "../../components/toast";
import { useWorkgroup } from "../../context/workgroup";
import { api } from "../../lib/api";
import { naira, plural } from "../../lib/format";
import { wgKey } from "../../lib/queries";
import type { Role } from "../../lib/types";

function RoleModal({ role, onClose }: { role: Role | "new"; onClose: () => void }) {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const editing = role !== "new";
  const [name, setName] = useState(editing ? role.name : "");
  const [salary, setSalary] = useState<number | null>(editing ? role.salary_kobo : null);
  const mutation = useMutation({
    mutationFn: () =>
      editing
        ? api.patch<Role>(`/workgroups/${workgroup.id}/roles/${role.id}`, { name, salary_kobo: salary ?? 0 })
        : api.post<Role>(`/workgroups/${workgroup.id}/roles`, { name, salary_kobo: salary ?? 0 }),
    onSuccess: (r) => {
      toast.success(editing ? `${r.name} updated` : `${r.name} created`);
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
      onClose();
    },
    onError: (e) => toast.error(e),
  });
  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title={editing ? `Edit ${role.name}` : "New role"}
      description={editing && role.staff_count ? `Changing the salary updates pay for ${plural(role.staff_count, "staff member")} who follow this role.` : "Staff you put in this role are paid its salary unless they have a personal salary."}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button loading={mutation.isPending} disabled={!name.trim() || salary === null} onClick={() => mutation.mutate()}>
            {editing ? "Save changes" : "Create role"}
          </Button>
        </>
      }
    >
      <form
        className="grid gap-4"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          mutation.mutate();
        }}
      >
        <Input label="Role name" placeholder="e.g. Drivers, Supervisors, Cashiers" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        <MoneyInput label="Monthly salary" valueKobo={salary} onChangeKobo={setSalary} />
      </form>
    </Modal>
  );
}

export default function Roles() {
  const workgroup = useWorkgroup();
  const toast = useToast();
  const qc = useQueryClient();
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const [deleting, setDeleting] = useState<Role | null>(null);
  const roles = useQuery({ queryKey: wgKey(workgroup.id, "roles"), queryFn: () => api.get<Role[]>(`/workgroups/${workgroup.id}/roles`) });
  const remove = useMutation({
    mutationFn: (r: Role) => api.delete(`/workgroups/${workgroup.id}/roles/${r.id}`),
    onSuccess: () => {
      toast.success("Role deleted", "Its staff keep their current salary.");
      setDeleting(null);
      qc.invalidateQueries({ queryKey: ["wg", workgroup.id] });
    },
    onError: (e) => toast.error(e),
  });
  const total = (roles.data ?? []).reduce((sum, r) => sum + r.salary_kobo * r.staff_count, 0);

  return (
    <div>
      <PageHeader
        title="Roles & pay"
        description="Set a salary once for everyone in a role — drivers, supervisors, cashiers. Change it here and everyone in the role follows."
        action={<Button onClick={() => setEditing("new")}>New role</Button>}
      />
      <Card className="overflow-hidden">
        <CardHeader title="Salary roles" description={roles.data?.length ? `${naira(total)} per month across roles (before personal salaries)` : undefined} />
        {roles.error ? (
          <ErrorState error={roles.error} onRetry={() => roles.refetch()} />
        ) : roles.isLoading ? (
          <div className="grid gap-2 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-11" />)}</div>
        ) : !roles.data?.length ? (
          <EmptyState icon={<ShieldCheck size={20} />} title="No roles yet" action={<Button onClick={() => setEditing("new")}>Create a role</Button>}>
            Roles are optional. They save time when many people earn the same amount.
          </EmptyState>
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Role</Th>
                <Th align="right">Monthly salary</Th>
                <Th align="right">Staff</Th>
                <Th align="right">Monthly total</Th>
                <Th />
              </tr>
            </thead>
            <tbody>
              {roles.data.map((r) => (
                <tr key={r.id} className="hover:bg-soft/40">
                  <Td className="font-medium">{r.name}</Td>
                  <Td align="right">{naira(r.salary_kobo)}</Td>
                  <Td align="right">
                    <Link to={`/app/staff`} className="hover:underline">{r.staff_count}</Link>
                  </Td>
                  <Td align="right" className="text-ink-2">{naira(r.salary_kobo * r.staff_count)}</Td>
                  <Td align="right">
                    <div className="flex justify-end gap-1">
                      <IconButton label={`Edit ${r.name}`} onClick={() => setEditing(r)}>
                        <Pencil size={15} />
                      </IconButton>
                      <IconButton label={`Delete ${r.name}`} onClick={() => setDeleting(r)}>
                        <Trash2 size={15} />
                      </IconButton>
                    </div>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <p className="mt-4 text-[13px] text-ink-3">
        Assign roles from the <Link to="/app/staff" className="font-semibold text-brand-strong hover:underline dark:text-brand">Staff</Link> page — select several people at once to move them together.
      </p>

      {editing && <RoleModal role={editing} onClose={() => setEditing(null)} />}
      <Modal
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        size="sm"
        title={`Delete ${deleting?.name}?`}
        description={deleting?.staff_count ? `${plural(deleting.staff_count, "staff member")} keep their current salary of ${naira(deleting.salary_kobo)}, set as a personal salary.` : "No staff are in this role."}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleting(null)}>Cancel</Button>
            <Button variant="danger" loading={remove.isPending} onClick={() => deleting && remove.mutate(deleting)}>Delete role</Button>
          </>
        }
      />
    </div>
  );
}
