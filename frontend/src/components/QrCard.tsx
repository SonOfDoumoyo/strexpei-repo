import { useRef } from "react";
import { QRCodeCanvas, QRCodeSVG } from "qrcode.react";
import { Download, MessageCircle, Printer } from "lucide-react";
import type { Workgroup } from "../lib/types";
import { Button, CopyButton, cx } from "./ui";

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

export function printPoster(workgroup: Workgroup, svgMarkup: string) {
  const win = window.open("", "_blank", "width=820,height=1100");
  if (!win) return;
  const name = escapeHtml(workgroup.name);
  win.document.write(`<!doctype html><html><head><title>${name} — payroll registration</title>
<meta charset="utf-8"><style>
@page{size:A4;margin:18mm}*{box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,sans-serif;color:#151412;margin:0;text-align:center}
.wrap{border:2px solid #151412;border-radius:28px;padding:44px 40px;max-width:640px;margin:0 auto}
.brand{font-weight:800;letter-spacing:.24em;font-size:14px}.brand span{color:#B8904A}
h1{font-size:40px;line-height:1.05;margin:28px 0 10px;letter-spacing:-.03em}p{font-size:16px;line-height:1.6;color:#4a443c;margin:0}
.qr{margin:34px auto 22px;width:300px;height:300px;padding:18px;border:1px solid #e1d7c8;border-radius:22px}.qr svg{width:100%;height:100%}
.url{font-family:ui-monospace,Menlo,monospace;font-size:14px;background:#f7f3ec;border-radius:12px;padding:12px 14px;word-break:break-all;margin-top:6px}
ol{text-align:left;max-width:420px;margin:28px auto 0;padding-left:22px;font-size:15px;line-height:1.9;color:#2b2722}.foot{margin-top:30px;font-size:12px;color:#8a8070}
</style></head><body><div class="wrap"><div class="brand">STREIXPEI<span>.</span></div>
<h1>${name} payroll registration</h1><p>Scan with your phone camera to add your bank details for salary payments.</p>
<div class="qr">${svgMarkup}</div><div class="url">${escapeHtml(workgroup.join_url)}</div>
<ol><li>Scan the code or open the link.</li><li>Enter the staff ID your finance team gave you.</li><li>Add your name, email and bank account. We verify it instantly.</li></ol>
<div class="foot">No app or account needed. Never share your card PIN or passwords — this form never asks for them.</div></div>
<script>window.onload=function(){setTimeout(function(){window.print()},250)}</script></body></html>`);
  win.document.close();
}

export function QrActions({ workgroup, className }: { workgroup: Workgroup; className?: string }) {
  const hidden = useRef<HTMLDivElement>(null);

  function downloadPng() {
    const canvas = hidden.current?.querySelector("canvas");
    if (!canvas) return;
    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/png");
    a.download = `${workgroup.name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-onboarding-qr.png`;
    a.click();
  }

  const shareText = encodeURIComponent(`Hi team, please register for ${workgroup.name} payroll here. You'll need the staff ID we gave you: ${workgroup.join_url}`);

  return (
    <div className={cx("flex flex-wrap justify-center gap-2", className)}>
      <div ref={hidden} className="hidden" aria-hidden>
        <QRCodeCanvas value={workgroup.join_url} size={1024} level="M" marginSize={4} fgColor="#151412" bgColor="#FFFFFF" />
        <QRCodeSVG value={workgroup.join_url} size={300} level="M" marginSize={0} fgColor="#151412" bgColor="#FFFFFF" />
      </div>
      <CopyButton text={workgroup.join_url} label="Copy link" />
      <Button size="sm" variant="secondary" icon={<Download size={14} />} onClick={downloadPng}>
        QR image
      </Button>
      <Button size="sm" variant="secondary" icon={<Printer size={14} />} onClick={() => printPoster(workgroup, hidden.current?.querySelector("svg")?.outerHTML ?? "")}>
        Print poster
      </Button>
      <a
        href={`https://wa.me/?text=${shareText}`}
        target="_blank"
        rel="noreferrer"
        className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-line bg-raised px-3 text-[13px] font-semibold transition hover:border-line-strong"
      >
        <MessageCircle size={14} /> WhatsApp
      </a>
    </div>
  );
}

export function QrCard({ workgroup, size = 196, className, actions = true }: { workgroup: Workgroup; size?: number; className?: string; actions?: boolean }) {
  const inactive = !workgroup.invite_active;
  return (
    <div className={cx("flex flex-col items-center", className)}>
      <div className={cx("relative rounded-[22px] border border-line bg-white p-4", inactive && "opacity-40")}>
        <QRCodeSVG value={workgroup.join_url} size={size} level="M" marginSize={0} fgColor="#151412" bgColor="#FFFFFF" title={`QR code for ${workgroup.join_url}`} />
        {inactive && <span className="absolute inset-0 grid place-items-center rounded-[22px] text-[13px] font-semibold text-[#151412]">Paused</span>}
      </div>
      {actions && <QrActions workgroup={workgroup} className="mt-5" />}
    </div>
  );
}
