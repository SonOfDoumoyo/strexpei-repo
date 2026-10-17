import { type FormEvent, type ReactNode, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { ApiError } from "../lib/api";
import { Button, Input, Modal } from "./ui";

export function PasswordModal({
  open,
  onClose,
  title,
  description,
  confirmLabel,
  onConfirm,
  danger,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  confirmLabel: string;
  onConfirm: (password: string) => Promise<unknown>;
  danger?: boolean;
  children?: ReactNode;
}) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    if (!password || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onConfirm(password);
      setPassword("");
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!busy) {
          setPassword("");
          setError(null);
          onClose();
        }
      }}
      size="sm"
      title={title}
      description={description}
      footer={
        <>
          <Button variant="ghost" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} loading={busy} disabled={!password} onClick={() => submit()}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="grid gap-4">
        {children}
        <Input
          label="Your password"
          type="password"
          autoComplete="current-password"
          autoFocus
          leading={<LockKeyhole size={15} />}
          value={password}
          error={error}
          onChange={(e) => setPassword(e.target.value)}
        />
      </form>
    </Modal>
  );
}
