import { Suspense, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, Building2, LogOut, Menu as MenuIcon, Moon, Receipt, SlidersHorizontal, Sun, Users, X } from "lucide-react";
import { Logo } from "../../components/Logo";
import { cx, IconButton, PageLoader } from "../../components/ui";
import { useAuth } from "../../context/auth";
import { useTheme } from "../../context/theme";

const NAV = [
  { to: "/admin", label: "Revenue", icon: BarChart3, end: true },
  { to: "/admin/users", label: "Managers", icon: Users },
  { to: "/admin/workgroups", label: "Workgroups", icon: Building2 },
  { to: "/admin/payroll", label: "Payroll runs", icon: Receipt },
  { to: "/admin/pricing", label: "Pricing & fees", icon: SlidersHorizontal },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { mode, toggleMode } = useTheme();
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen bg-shell">
      <aside className={cx("fixed inset-y-0 left-0 z-[90] flex w-[248px] flex-col border-r border-line bg-surface transition-transform lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
        <div className="flex h-[68px] items-center justify-between px-5">
          <Logo to="/admin" />
          <IconButton label="Close" className="lg:hidden" onClick={() => setOpen(false)}><X size={18} /></IconButton>
        </div>
        <p className="px-6 pb-2 text-[12px] font-medium text-ink-3">Platform console</p>
        <nav className="grid gap-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => cx("flex items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] font-medium", isActive ? "bg-soft text-ink" : "text-ink-2 hover:bg-ink/[0.04]")}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-line p-3">
          <p className="truncate px-3 text-[13px] font-semibold">{user?.full_name}</p>
          <p className="truncate px-3 text-[12px] text-ink-3">{user?.email}</p>
          <button type="button" onClick={() => void logout()} className="mt-2 flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13.5px] font-medium text-ink-2 hover:bg-ink/[0.04]">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>
      {open && <button type="button" aria-label="Close menu" className="fixed inset-0 z-[80] bg-black/30 lg:hidden" onClick={() => setOpen(false)} />}
      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-50 flex h-[64px] items-center gap-2 border-b border-line bg-shell/85 px-4 backdrop-blur-xl sm:px-6 lg:px-10">
          <IconButton label="Open menu" className="lg:hidden" onClick={() => setOpen(true)}><MenuIcon size={19} /></IconButton>
          <span className="text-[13px] font-medium text-ink-3">Streixpei admin</span>
          <IconButton label="Toggle dark mode" className="ml-auto" onClick={toggleMode}>{mode === "dark" ? <Sun size={18} /> : <Moon size={18} />}</IconButton>
        </header>
        <main className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 sm:py-8 lg:px-10">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
