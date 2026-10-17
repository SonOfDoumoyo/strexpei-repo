import { type ReactNode, useEffect, useRef, useState } from "react";
import { cx } from "./ui";

/*
 * Small SVG charts following the house rules: thin marks (≤24px bars, 4px
 * rounded data end, square at the baseline), 2px lines, hairline recessive
 * grid, one axis, text in ink tokens (never the series colour), a hover
 * tooltip on every mark, and a legend whenever there are two series.
 * Series colours: --c-series-1 (gold) and --c-series-2 (blue), validated
 * for colour-vision deficiency and contrast in both light and dark mode.
 */

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(600);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  const f = value / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * exp;
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: ReactNode }) {
  const left = Math.min(Math.max(x, 70), width - 70);
  return (
    <div className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-xl border border-line bg-raised px-3 py-2 text-[12px] shadow-[var(--shadow-pop)]" style={{ left, top: y - 10 }}>
      {children}
    </div>
  );
}

const PAD = { top: 16, right: 12, bottom: 28, left: 52 };

export function BarChart({
  data,
  format,
  height = 240,
  series = 1,
  label,
}: {
  data: { key: string; label: string; values: number[]; detail?: ReactNode }[];
  format: (v: number) => string;
  height?: number;
  series?: 1 | 2;
  label: string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const totals = data.map((d) => d.values.slice(0, series).reduce((a, b) => a + b, 0));
  const max = niceMax(Math.max(...totals, 0));
  const innerW = Math.max(10, width - PAD.left - PAD.right);
  const innerH = height - PAD.top - PAD.bottom;
  const band = innerW / Math.max(1, data.length);
  const barW = Math.min(24, band * 0.55);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const colors = ["var(--c-series-1)", "var(--c-series-2)"];

  return (
    <div ref={ref} className="relative w-full" role="img" aria-label={label}>
      <svg width={width} height={height} className="block overflow-visible">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--c-line)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="num fill-[var(--c-ink-3)] text-[11px]">
              {format(t)}
            </text>
          </g>
        ))}
        {data.map((d, i) => {
          const cx0 = PAD.left + band * i + band / 2;
          let acc = 0;
          return (
            <g key={d.key}>
              {d.values.slice(0, series).map((v, s) => {
                if (v <= 0) return null;
                const top = y(acc + v);
                const bottom = y(acc);
                acc += v;
                const h = Math.max(0, bottom - top - (s > 0 ? 2 : 0));
                const isTop = s === series - 1 || d.values.slice(s + 1, series).every((x) => x <= 0);
                const r = isTop ? Math.min(4, h) : 0;
                const x0 = cx0 - barW / 2;
                const path = `M${x0},${bottom}V${top + r}${r ? `Q${x0},${top} ${x0 + r},${top}` : ""}H${x0 + barW - r}${r ? `Q${x0 + barW},${top} ${x0 + barW},${top + r}` : ""}V${bottom}Z`;
                return <path key={s} d={path} fill={colors[s]} opacity={hover === null || hover === i ? 1 : 0.45} />;
              })}
              <text x={cx0} y={height - 8} textAnchor="middle" className="fill-[var(--c-ink-3)] text-[11px]">
                {d.label}
              </text>
              <rect x={cx0 - band / 2} y={PAD.top} width={band} height={innerH} fill="transparent" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
            </g>
          );
        })}
      </svg>
      {hover !== null && data[hover] && (
        <Tooltip x={PAD.left + band * hover + band / 2} y={y(totals[hover])} width={width}>
          <p className="font-semibold">{data[hover].label}</p>
          {data[hover].detail ?? <p className="num text-ink-2">{format(totals[hover])}</p>}
        </Tooltip>
      )}
    </div>
  );
}

export function LineChart({ data, format, height = 200, label }: { data: { key: string; label: string; value: number }[]; format: (v: number) => string; height?: number; label: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const max = niceMax(Math.max(...data.map((d) => d.value), 0));
  const innerW = Math.max(10, width - PAD.left - PAD.right);
  const innerH = height - PAD.top - PAD.bottom;
  const x = (i: number) => PAD.left + (data.length <= 1 ? innerW / 2 : (innerW * i) / (data.length - 1));
  const y = (v: number) => PAD.top + innerH - (v / max) * innerH;
  const line = data.map((d, i) => `${i ? "L" : "M"}${x(i)},${y(d.value)}`).join("");
  const area = data.length ? `${line}L${x(data.length - 1)},${y(0)}L${x(0)},${y(0)}Z` : "";
  const last = data.length - 1;
  return (
    <div ref={ref} className="relative w-full" role="img" aria-label={label}>
      <svg
        width={width}
        height={height}
        className="block overflow-visible"
        onMouseMove={(e) => {
          const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
          const px = e.clientX - rect.left;
          const idx = Math.round(((px - PAD.left) / innerW) * (data.length - 1));
          setHover(Math.max(0, Math.min(data.length - 1, idx)));
        }}
        onMouseLeave={() => setHover(null)}
      >
        {[0, 0.5, 1].map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(t * max)} y2={y(t * max)} stroke="var(--c-line)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t * max)} dy="0.32em" textAnchor="end" className="num fill-[var(--c-ink-3)] text-[11px]">
              {format(t * max)}
            </text>
          </g>
        ))}
        <path d={area} fill="var(--c-series-1)" opacity={0.1} />
        <path d={line} fill="none" stroke="var(--c-series-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {data.map((d, i) => (
          <text key={d.key} x={x(i)} y={height - 8} textAnchor="middle" className="fill-[var(--c-ink-3)] text-[11px]">
            {data.length > 8 && i % 2 === 1 ? "" : d.label}
          </text>
        ))}
        {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={y(0)} stroke="var(--c-line-strong)" strokeWidth={1} />}
        {last >= 0 && (
          <>
            <circle cx={x(hover ?? last)} cy={y(data[hover ?? last].value)} r={6} fill="var(--c-surface)" />
            <circle cx={x(hover ?? last)} cy={y(data[hover ?? last].value)} r={4} fill="var(--c-series-1)" />
            {hover === null && (
              <text x={x(last) - 8} y={y(data[last].value) - 12} textAnchor="end" className="num fill-[var(--c-ink)] text-[12px] font-semibold">
                {format(data[last].value)}
              </text>
            )}
          </>
        )}
      </svg>
      {hover !== null && data[hover] && (
        <Tooltip x={x(hover)} y={y(data[hover].value)} width={width}>
          <p className="font-semibold">{data[hover].label}</p>
          <p className="num text-ink-2">{format(data[hover].value)}</p>
        </Tooltip>
      )}
    </div>
  );
}

export function HBars({ rows, format, label }: { rows: { label: string; value: number; sub?: string }[]; format: (v: number) => string; label: string }) {
  const max = Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="grid gap-3.5" aria-label={label}>
      {rows.map((r) => (
        <li key={r.label} className="grid gap-1.5" title={`${r.label}: ${format(r.value)}`}>
          <div className="flex items-baseline justify-between gap-3 text-[13px]">
            <span className="truncate font-medium">
              {r.label} {r.sub && <span className="font-normal text-ink-3">{r.sub}</span>}
            </span>
            <span className="num shrink-0 text-ink-2">{format(r.value)}</span>
          </div>
          <div className="h-2.5 rounded-full bg-ink/[0.05]">
            <div className="h-full rounded-r-[4px] rounded-l-full" style={{ width: `${Math.max(2, (r.value / max) * 100)}%`, background: "var(--c-series-1)" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-4 text-[12.5px] text-ink-2">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function DataTableToggle({ children, table }: { children: ReactNode; table: ReactNode }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <button type="button" onClick={() => setShowTable((v) => !v)} className={cx("text-[12px] font-semibold text-ink-3 hover:text-ink")}>
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {showTable ? table : children}
    </div>
  );
}
