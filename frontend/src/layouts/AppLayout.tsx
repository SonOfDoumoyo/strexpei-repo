import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  BarChart3,
  Bell,
  Building2,
  Check,
  ChevronsUpDown,
  CreditCard,
  IdCard,
  LayoutGrid,
  LogOut,
  Menu as MenuIcon,
  Moon,
  Plus,
  QrCode,
  Receipt,
  Search,
  Settings as SettingsIcon,
  ShieldCheck,
  Sparkles,
  Sun,
  Users,
  Wallet,
  X,
} from "lucide-react";
import { Logo } from "../components/Logo";
import { SpiChat } from "../components/SpiChat";
import { Avatar, Badge, cx, IconButton, Menu, MenuItem, PageLoader } from "../components/ui";
import { useAuth } from "../context/auth";
import { useTheme } from "../context/theme";
import { useWorkgroups } from "../context/workgroup";
import { daysUntil } from "../lib/format";
import { useMeta, useUnreadCount } from "../lib/queries";

type NavItem = { to: string; label: string; icon: typeof Users; end?: boolean };
const NAV: { heading?: string; items: NavItem[] }[] = [
  { items: [{ to: "/app", label: "Overview", icon: LayoutGrid, end: true }] },
  {
    heading: "People",
    items: [
      { to: "/app/staff", label: "Staff", icon: Users },
      { to: "/app/staff-ids", label: "Staff IDs", icon: IdCard },
      { to: "/app/onboarding", label: "Onboarding link", icon: QrCode },
      { to: "/app/roles", label: "Roles & pay", icon: ShieldCheck },
    ],
  },
  {
    heading: "Money",
    items: [
      { to: "/app/payroll", label: "Payroll", icon: Receipt },
      { to: "/app/wallet", label: "Wallet", icon: Wallet },
      { to: "/app/billing", label: "Plan & billing", icon: CreditCard },
    ],
  },
  {
    heading: "Insights",
    items: [
      { to: "/app/analytics", label: "Analytics", icon: BarChart3 },
      { to: "/app/activity", label: "Activity", icon: Activity },
    ],
  },
];

function WorkgroupSwitcher({ onNavigate }: { onNavigate: () => void }) {
  const { workgroups, workgroup, select } = useWorkgroups();
  const navigate = useNavigate();
  return (
    <Menu
      align="left"
      width={248}
      trigger={({ toggle, open }) => (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex w-full items-center gap-3 rounded-2xl border border-line bg-raised px-3 py-2.5 text-left transition hover:border-line-strong"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-soft text-[12px] font-bold text-brand-strong dark:text-brand">
            {workgroup ? workgroup.name.slice(0, 2).toUpperCase() : <Building2 size={15} />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[13.5px] font-semibold">{workgroup?.name ?? "No workgroup yet"}</span>
            <span className="block truncate text-[12px] text-ink-3">
              {workgroup ? `${workgroup.headcount} staff seats` : "Create one to start"}
            </span>
          </span>
          <ChevronsUpDown size={15} className="shrink-0 text-ink-3" />
        </button>
      )}
    >
      {(close) => (
        <>
          <p className="px-3 pb-1 pt-2 text-[12px] font-medium text-ink-3">Workgroups</p>
          {workgroups.map((w) => (
            <MenuItem
              key={w.id}
              icon={<span className="flex h-6 w-6 items-center justify-center rounded-md bg-soft text-[10px] font-bold">{w.name.slice(0, 2).toUpperCase()}</span>}
              onClick={() => {
                select(w.id);
                close();
                onNavigate();
                navigate("/app");
              }}
            >
              <span className="flex-1 truncate">{w.name}</span>
              {w.id === workgroup?.id && <Check size={15} className="text-brand" />}
            </MenuItem>
          ))}
          <div className="my-1 border-t border-line" />
          <MenuItem icon={<Plus size={16} />} to="/app/workgroups/new" onClick={() => { close(); onNavigate(); }}>
            New workgroup
          </MenuItem>
        </>
      )}
    </Menu>
  );
}

function Sidebar({ open, onClose, onOpenSpi }: { open: boolean; onClose: () => void; onOpenSpi: () => void }) {
  const { user, logout } = useAuth();
  return (
    <>
      <aside
        className={cx(
          "fixed inset-y-0 left-0 z-[90] flex w-[268px] flex-col border-r border-line bg-surface transition-transform duration-200 lg:translate-x-0",
          open ? "translate-x-0 shadow-[var(--shadow-pop)]" : "-translate-x-full",
        )}
        aria-label="Main navigation"
      >
        <div className="flex h-[68px] items-center justify-between px-5">
          <Logo to="/app" />
          <IconButton label="Close menu" onClick={onClose} className="lg:hidden">
            <X size={18} />
          </IconButton>
        </div>
        <div className="px-4 pb-3">
          <WorkgroupSwitcher onNavigate={onClose} />
        </div>
        <nav className="scrollbar-thin flex-1 overflow-y-auto px-3 pb-4">
          {NAV.map((group, i) => (
            <div key={i} className="mt-3 first:mt-1">
              {group.heading && <p className="px-3 pb-1.5 pt-2 text-[12px] font-medium text-ink-3">{group.heading}</p>}
              <div className="grid gap-0.5">
                {group.items.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={onClose}
                    className={({ isActive }) =>
                      cx(
                        "group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] font-medium transition",
                        isActive ? "bg-soft text-ink" : "text-ink-2 hover:bg-ink/[0.04] hover:text-ink",
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span className={cx("absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-brand transition-opacity", isActive ? "opacity-100" : "opacity-0")} />
                        <Icon size={17} strokeWidth={1.9} className={isActive ? "text-brand-strong dark:text-brand" : "text-ink-3 group-hover:text-ink-2"} />
                        {label}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-line p-3">
          <button
            type="button"
            onClick={() => {
              onClose();
              onOpenSpi();
            }}
            className="mb-2 flex w-full items-center gap-3 rounded-xl bg-ink px-3 py-2.5 text-left text-[13.5px] font-semibold text-shell transition hover:opacity-90 dark:bg-raised dark:text-ink"
          >
            <Sparkles size={16} className="text-brand" />
            Ask SPI
            <kbd className="ml-auto rounded-md border border-white/15 px-1.5 text-[10.5px] font-medium text-white/60 dark:border-line dark:text-ink-3">⌘K</kbd>
          </button>
          <Menu
            align="left"
            side="top"
            width={244}
            trigger={({ toggle }) => (
              <button type="button" onClick={toggle} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition hover:bg-ink/[0.04]">
                <Avatar name={user?.full_name} size={34} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-semibold">{user?.full_name}</span>
                  <span className="block truncate text-[12px] text-ink-3">{user?.email}</span>
                </span>
              </button>
            )}
          >
            {(close) => (
              <>
                <MenuItem icon={<SettingsIcon size={16} />} to="/app/settings" onClick={() => { close(); onClose(); }}>
                  Settings
                </MenuItem>
                <MenuItem icon={<LogOut size={16} />} onClick={() => { close(); void logout(); }}>
                  Sign out
                </MenuItem>
              </>
            )}
          </Menu>
        </div>
      </aside>
      {open && <button type="button" aria-label="Close navigation" onClick={onClose} className="animate-fade fixed inset-0 z-[80] bg-black/35 lg:hidden" />}
    </>
  );
}

const PALETTE_ITEMS = [
  ...NAV.flatMap((g) => g.items.map((i) => ({ to: i.to, label: i.label }))),
  { to: "/app/payroll", label: "Prepare payroll" },
  { to: "/app/wallet", label: "Fund wallet" },
  { to: "/app/staff-ids", label: "Generate staff IDs" },
  { to: "/app/notifications", label: "Notifications" },
  { to: "/app/settings", label: "Settings" },
  { to: "/app/workgroups/new", label: "New workgroup" },
];

function CommandPalette({ open, onClose, onAsk }: { open: boolean; onClose: () => void; onAsk: (q: string) => void }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (open) {
      setQuery("");
      setIndex(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pages = PALETTE_ITEMS.filter((i, idx, arr) => arr.findIndex((x) => x.label === i.label) === idx).filter((i) => !q || i.label.toLowerCase().includes(q));
    return [...(q ? [{ to: "", label: `Ask SPI: “${query.trim()}”`, ask: true }] : []), ...pages.slice(0, 8).map((p) => ({ ...p, ask: false }))];
  }, [query]);
  if (!open) return null;
  const choose = (i: number) => {
    const item = results[i];
    if (!item) return;
    onClose();
    if (item.ask) onAsk(query.trim());
    else navigate(item.to);
  };
  return (
    <div className="fixed inset-0 z-[320] flex items-start justify-center p-4 pt-[12vh]">
      <div className="animate-fade absolute inset-0 bg-[#0b0906]/45" onClick={onClose} />
      <div className="animate-pop relative w-full max-w-lg overflow-hidden rounded-[22px] border border-line bg-surface shadow-[var(--shadow-pop)]">
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search size={17} className="text-ink-3" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setIndex(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(results.length - 1, i + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(0, i - 1));
              } else if (e.key === "Enter") {
                e.preventDefault();
                choose(index);
              } else if (e.key === "Escape") onClose();
            }}
            placeholder="Jump to a page or ask SPI…"
            aria-label="Search"
            className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-ink-3"
          />
          <kbd className="rounded-md border border-line px-1.5 text-[11px] text-ink-3">Esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-2" role="listbox">
          {results.map((r, i) => (
            <li key={r.label} role="option" aria-selected={i === index}>
              <button
                type="button"
                onMouseEnter={() => setIndex(i)}
                onClick={() => choose(i)}
                className={cx("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[14px]", i === index ? "bg-soft text-ink" : "text-ink-2")}
              >
                {r.ask ? <Sparkles size={16} className="text-brand" /> : <span className="h-1.5 w-1.5 rounded-full bg-ink-3" />}
                <span className="truncate">{r.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Banners() {
  const { workgroup } = useWorkgroups();
  const meta = useMeta();
  const location = useLocation();
  const sub = workgroup?.subscription;
  const items: { tone: "warn" | "bad" | "info"; text: string; cta?: { to: string; label: string } }[] = [];
  if (sub && !sub.usable) {
    items.push({ tone: "bad", text: sub.status === "expired" && sub.trial_ends_at && !sub.current_period_end ? "Your free trial has ended. Staff onboarding and payroll are paused until you subscribe." : "Your subscription has ended. Staff onboarding and payroll are paused.", cta: { to: "/app/billing", label: "Choose a plan" } });
  } else if (sub?.status === "past_due") {
    items.push({ tone: "warn", text: "We couldn't renew your subscription. Pay now to avoid a pause in payroll.", cta: { to: "/app/billing", label: "Pay now" } });
  } else if (sub?.status === "trialing") {
    const days = daysUntil(sub.trial_ends_at);
    if (days !== null && days <= 5)
      items.push({ tone: "info", text: `Your free trial ends in ${days <= 0 ? "less than a day" : `${days} day${days === 1 ? "" : "s"}`}.`, cta: { to: "/app/billing", label: "Subscribe" } });
  }
  if (location.pathname.startsWith("/app/billing")) items.length = 0;
  return (
    <>
      {meta.data?.payments_sandbox && (
        <div className="border-b border-warn/20 bg-warn-soft px-4 py-1.5 text-center text-[12.5px] font-medium text-warn">Test mode — payments and transfers are simulated. No real money moves.</div>
      )}
      {items.map((b) => (
        <div
          key={b.text}
          className={cx(
            "flex flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b px-4 py-2 text-center text-[13px]",
            b.tone === "bad" ? "border-bad/20 bg-bad-soft text-bad" : b.tone === "warn" ? "border-warn/20 bg-warn-soft text-warn" : "border-brand/20 bg-brand-soft text-ink",
          )}
        >
          <span className="font-medium">{b.text}</span>
          {b.cta && (
            <Link to={b.cta.to} className="font-semibold underline underline-offset-2">
              {b.cta.label}
            </Link>
          )}
        </div>
      ))}
    </>
  );
}

export function AppLayout() {
  const [navOpen, setNavOpen] = useState(false);
  const [spiOpen, setSpiOpen] = useState(false);
  const [spiPrompt, setSpiPrompt] = useState<string | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { user } = useAuth();
  const { mode, toggleMode } = useTheme();
  const { workgroup } = useWorkgroups();
  const unread = useUnreadCount(Boolean(user));
  const location = useLocation();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [location.pathname]);

  const openSpi = useCallback((prompt?: string) => {
    setSpiPrompt(prompt ?? null);
    setSpiOpen(true);
  }, []);

  const count = unread.data?.unread ?? 0;
  const onAssistantPage = location.pathname === "/app/assistant";

  return (
    <div className="min-h-screen bg-shell">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[500] focus:rounded-lg focus:bg-ink focus:px-3 focus:py-2 focus:text-shell">
        Skip to content
      </a>
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} onOpenSpi={() => openSpi()} />
      <div className="lg:pl-[268px]">
        <header className="no-print sticky top-0 z-[60] border-b border-line bg-shell/85 backdrop-blur-xl">
          <div className="flex h-[64px] items-center gap-2 px-4 sm:px-6 lg:px-10">
            <IconButton label="Open menu" onClick={() => setNavOpen(true)} className="lg:hidden">
              <MenuIcon size={19} />
            </IconButton>
            <span className="truncate text-[14px] font-semibold lg:hidden">{workgroup?.name ?? "Streixpei"}</span>
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="ml-auto hidden h-10 w-full max-w-sm items-center gap-2.5 rounded-xl border border-line bg-raised px-3.5 text-[13px] text-ink-3 transition hover:border-line-strong md:flex lg:ml-0"
            >
              <Search size={15} />
              Jump to a page or ask SPI…
              <kbd className="ml-auto rounded-md border border-line px-1.5 text-[10.5px]">⌘K</kbd>
            </button>
            <div className="ml-auto flex items-center gap-1">
              <IconButton label="Search" onClick={() => setPaletteOpen(true)} className="md:hidden">
                <Search size={18} />
              </IconButton>
              <IconButton label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"} onClick={toggleMode}>
                {mode === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </IconButton>
              <Link to="/app/notifications" aria-label={`Notifications${count ? `, ${count} unread` : ""}`} className="relative inline-flex h-9 w-9 items-center justify-center rounded-xl text-ink-2 transition hover:bg-ink/5 hover:text-ink">
                <Bell size={18} />
                {count > 0 && (
                  <span className="num absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-brand px-1 text-[10.5px] font-bold text-brand-ink ring-2 ring-shell">
                    {count > 99 ? "99+" : count}
                  </span>
                )}
              </Link>
              {workgroup?.subscription && (
                <Link to="/app/billing" className="ml-1 hidden sm:block">
                  <Badge tone={workgroup.subscription.status === "active" ? "brand" : workgroup.subscription.usable ? "neutral" : "bad"} dot={false}>
                    {workgroup.subscription.status === "trialing" ? "Free trial" : `${workgroup.subscription.plan.name} plan`}
                  </Badge>
                </Link>
              )}
            </div>
          </div>
        </header>
        <div className="no-print">
          <Banners />
        </div>
        <main id="main" className="mx-auto w-full max-w-[1240px] px-4 pb-24 pt-6 sm:px-6 sm:pt-8 lg:px-10 lg:py-10">
          <Suspense fallback={<PageLoader />}>
            <Outlet context={{ openSpi }} />
          </Suspense>
        </main>
      </div>

      {!onAssistantPage && !spiOpen && (
        <button
          type="button"
          onClick={() => openSpi()}
          className="no-print fixed bottom-5 right-5 z-[70] flex h-12 items-center lg:hidden gap-2 rounded-full bg-ink pl-4 pr-5 text-[13.5px] font-semibold text-shell shadow-[var(--shadow-pop)] transition hover:-translate-y-0.5 dark:bg-raised dark:text-ink dark:ring-1 dark:ring-line"
        >
          <Sparkles size={16} className="text-brand" /> Ask SPI
        </button>
      )}

      {spiOpen && (
        <div className="fixed inset-0 z-[260]">
          <div className="animate-fade absolute inset-0 bg-[#0b0906]/35" onClick={() => setSpiOpen(false)} />
          <aside role="dialog" aria-label="SPI assistant" className="animate-slide absolute inset-y-0 right-0 flex w-full max-w-[460px] flex-col border-l border-line bg-surface shadow-[var(--shadow-pop)]">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-brand dark:bg-raised">
                  <Sparkles size={17} />
                </span>
                <div>
                  <p className="text-[15px] font-semibold">SPI</p>
                  <p className="text-[12px] text-ink-3">{workgroup ? `Working in ${workgroup.name}` : "Your payroll assistant"}</p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Link to="/app/assistant" onClick={() => setSpiOpen(false)} className="rounded-lg px-2 py-1 text-[12.5px] font-medium text-ink-3 hover:text-ink">
                  Full screen
                </Link>
                <IconButton label="Close SPI" onClick={() => setSpiOpen(false)}>
                  <X size={18} />
                </IconButton>
              </div>
            </div>
            <div className="min-h-0 flex-1">
              <SpiChat workgroupId={workgroup?.id ?? null} compact onNavigate={() => setSpiOpen(false)} initialPrompt={spiPrompt} />
            </div>
          </aside>
        </div>
      )}

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onAsk={(q) => openSpi(q)} />
    </div>
  );
}
