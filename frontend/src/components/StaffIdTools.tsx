import { type DragEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileSpreadsheet, UploadCloud } from "lucide-react";
import { ApiError, api } from "../lib/api";
import { plural } from "../lib/format";
import type { IdsSummary, UploadReport, Workgroup } from "../lib/types";
import { useToast } from "./toast";
import { Button, cx, Input, Notice, Segmented, Textarea } from "./ui";

type ImportResult = { report: UploadReport; summary: IdsSummary };

export function downloadTemplate() {
  const csv = "Staff ID,Full name,Role,Salary\nEMP-001,Chidi Eze,Driver,150000\nEMP-002,Amaka Obi,Supervisor,220000\n";
  const href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = href;
  a.download = "streixpei-staff-ids-template.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(href), 1500);
}

export function SeatsError({ error }: { error: ApiError }) {
  if (error.code !== "seats_exceeded") return <Notice tone="bad">{error.message}</Notice>;
  return (
    <Notice
      tone="warn"
      title="Not enough staff seats"
      action={
        <Link to="/app/billing?seats=1" className="inline-flex h-9 items-center rounded-xl bg-ink px-3 text-[13px] font-semibold text-shell">
          Increase staff count
        </Link>
      }
    >
      {error.message}
    </Notice>
  );
}

export function ReportView({ report }: { report: UploadReport }) {
  return (
    <div className="grid gap-3 rounded-2xl border border-line bg-raised p-4 text-[13.5px]">
      <p className="flex items-center gap-2 font-semibold">
        <CheckCircle2 size={17} className="text-good" /> {plural(report.added_count, "staff ID")} added
      </p>
      {report.already_exists.length > 0 && (
        <p className="text-ink-2">
          {plural(report.already_exists.length, "ID")} already existed and were skipped: <span className="text-ink-3">{report.already_exists.slice(0, 8).join(", ")}{report.already_exists.length > 8 ? "…" : ""}</span>
        </p>
      )}
      {report.duplicates_in_file.length > 0 && (
        <p className="text-ink-2">
          {plural(report.duplicates_in_file.length, "duplicate")} in the file were ignored: <span className="text-ink-3">{report.duplicates_in_file.slice(0, 8).join(", ")}</span>
        </p>
      )}
      {report.invalid.length > 0 && (
        <div>
          <p className="text-warn">{plural(report.invalid.length, "row")} couldn't be used:</p>
          <ul className="mt-1 grid gap-0.5 text-[12.5px] text-ink-3">
            {report.invalid.slice(0, 6).map((row) => (
              <li key={`${row.line}-${row.value}`}>
                Line {row.line}{row.value ? ` (“${row.value}”)` : ""}: {row.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function useInvalidateIds(workgroupId: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["wg", workgroupId] });
    qc.invalidateQueries({ queryKey: ["workgroups"] });
  };
}

export function GenerateIds({ workgroup, remaining, onDone, compact }: { workgroup: Workgroup; remaining: number; onDone?: (codes: string[]) => void; compact?: boolean }) {
  const [count, setCount] = useState(String(Math.max(1, remaining)));
  const [codes, setCodes] = useState<string[] | null>(null);
  const invalidate = useInvalidateIds(workgroup.id);
  const toast = useToast();
  const n = Number(count);
  const mutation = useMutation({
    mutationFn: () => api.post<{ created: number; codes: string[]; summary: IdsSummary }>(`/workgroups/${workgroup.id}/staff-ids/generate`, { count: n }),
    onSuccess: (data) => {
      setCodes(data.codes);
      invalidate();
      toast.success(`${plural(data.created, "staff ID")} created`);
      onDone?.(data.codes);
    },
  });
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Input
          label="How many IDs?"
          type="number"
          min={1}
          max={Math.max(1, remaining)}
          className="num w-32"
          value={count}
          onChange={(e) => setCount(e.target.value)}
          hint={`${remaining} of ${workgroup.headcount} seats free`}
        />
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending} disabled={!n || n < 1} className="mb-6">
          Generate {n > 0 ? plural(n, "ID") : "IDs"}
        </Button>
      </div>
      {!compact && !codes && (
        <p className="text-[13px] leading-6 text-ink-2">
          Each ID looks like <span className="num rounded-md bg-soft px-1.5 py-0.5 font-semibold text-ink">{workgroup.staff_id_prefix}-7K3M-Q9TD</span>, is unique across Streixpei, and avoids look-alike characters (no O/0 or I/1 mix-ups). Give one to each staff member.
        </p>
      )}
      {mutation.error && <SeatsError error={mutation.error as ApiError} />}
      {codes && (
        <div className="rounded-2xl border border-line bg-raised p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[13.5px] font-semibold">{plural(codes.length, "new ID")}</p>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" icon={<FileSpreadsheet size={14} />} onClick={() => api.download(`/workgroups/${workgroup.id}/staff-ids/export`, "staff-ids.xlsx", { format: "xlsx" })}>
                Excel
              </Button>
              <Button size="sm" variant="secondary" onClick={() => api.download(`/workgroups/${workgroup.id}/staff-ids/export`, "staff-ids.csv")}>
                CSV
              </Button>
            </div>
          </div>
          <div className="num mt-3 grid max-h-44 grid-cols-2 gap-1.5 overflow-y-auto text-[12.5px] font-semibold sm:grid-cols-3">
            {codes.slice(0, 60).map((c) => (
              <span key={c} className="rounded-lg bg-soft px-2 py-1.5 text-center tracking-wide">
                {c}
              </span>
            ))}
          </div>
          {codes.length > 60 && <p className="mt-2 text-[12px] text-ink-3">Download the file to see all {codes.length}.</p>}
        </div>
      )}
    </div>
  );
}

export function ImportIds({ workgroup, onDone }: { workgroup: Workgroup; onDone?: (r: ImportResult) => void }) {
  const [mode, setMode] = useState<"file" | "paste">("file");
  const [text, setText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const invalidate = useInvalidateIds(workgroup.id);
  const toast = useToast();

  const upload = useMutation({
    mutationFn: (file: File) => api.upload<ImportResult>(`/workgroups/${workgroup.id}/staff-ids/upload`, file),
    onSuccess: (data) => done(data),
  });
  const paste = useMutation({
    mutationFn: () => api.post<ImportResult>(`/workgroups/${workgroup.id}/staff-ids/paste`, { text }),
    onSuccess: (data) => {
      setText("");
      done(data);
    },
  });
  const done = (data: ImportResult) => {
    setResult(data);
    invalidate();
    if (data.report.added_count) toast.success(`${plural(data.report.added_count, "staff ID")} imported`);
    onDone?.(data);
  };
  const error = (upload.error ?? paste.error) as ApiError | null;

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) upload.mutate(file);
  }

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented
          size="sm"
          value={mode}
          onChange={setMode}
          options={[
            { value: "file", label: "Upload a file" },
            { value: "paste", label: "Paste IDs" },
          ]}
        />
        <button type="button" onClick={downloadTemplate} className="text-[12.5px] font-semibold text-brand-strong hover:underline dark:text-brand">
          Download template
        </button>
      </div>
      {mode === "file" ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cx("rounded-2xl border-2 border-dashed px-6 py-9 text-center transition", dragging ? "border-brand bg-brand-soft/60" : "border-line bg-raised")}
        >
          <UploadCloud size={26} className="mx-auto text-brand-strong dark:text-brand" />
          <p className="mt-3 text-[14px] font-semibold">Drop your staff list here</p>
          <p className="mt-1 text-[12.5px] leading-5 text-ink-3">
            Excel (.xlsx) or CSV. We look for a “Staff ID” column; name, role and salary columns are optional.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.txt,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = "";
            }}
          />
          <Button variant="secondary" size="sm" className="mt-4" loading={upload.isPending} onClick={() => fileRef.current?.click()}>
            Choose file
          </Button>
        </div>
      ) : (
        <div className="grid gap-3">
          <Textarea
            label="Staff IDs"
            hint="One per line, or separated by commas."
            placeholder={"EMP-001\nEMP-002\nEMP-003"}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="num min-h-36"
          />
          <div>
            <Button onClick={() => paste.mutate()} loading={paste.isPending} disabled={!text.trim()}>
              Add these IDs
            </Button>
          </div>
        </div>
      )}
      {error && <SeatsError error={error} />}
      {result && <ReportView report={result.report} />}
    </div>
  );
}
