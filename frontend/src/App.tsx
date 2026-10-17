import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/auth";
import { useWorkgroups } from "./context/workgroup";
import { AppLayout } from "./layouts/AppLayout";
import { LogoMark } from "./components/Logo";
import { PageLoader } from "./components/ui";

const Landing = lazy(() => import("./pages/public/Landing"));
const Join = lazy(() => import("./pages/public/Join"));
const DevCheckout = lazy(() => import("./pages/public/DevCheckout"));
const NotFound = lazy(() => import("./pages/public/NotFound"));
const Login = lazy(() => import("./pages/auth/Login"));
const Signup = lazy(() => import("./pages/auth/Signup"));
const VerifyEmail = lazy(() => import("./pages/auth/VerifyEmail"));
const ForgotPassword = lazy(() => import("./pages/auth/ForgotPassword"));
const Dashboard = lazy(() => import("./pages/app/Dashboard"));
const NewWorkgroup = lazy(() => import("./pages/app/NewWorkgroup"));
const Staff = lazy(() => import("./pages/app/Staff"));
const StaffIds = lazy(() => import("./pages/app/StaffIds"));
const Onboarding = lazy(() => import("./pages/app/Onboarding"));
const Roles = lazy(() => import("./pages/app/Roles"));
const Payroll = lazy(() => import("./pages/app/Payroll"));
const PayrollRun = lazy(() => import("./pages/app/PayrollRun"));
const Wallet = lazy(() => import("./pages/app/Wallet"));
const Billing = lazy(() => import("./pages/app/Billing"));
const Analytics = lazy(() => import("./pages/app/Analytics"));
const Activity = lazy(() => import("./pages/app/Activity"));
const Notifications = lazy(() => import("./pages/app/Notifications"));
const Assistant = lazy(() => import("./pages/app/Assistant"));
const Settings = lazy(() => import("./pages/app/Settings"));
const PaymentCallback = lazy(() => import("./pages/app/PaymentCallback"));
const AdminLayout = lazy(() => import("./pages/admin/AdminLayout"));
const AdminOverview = lazy(() => import("./pages/admin/AdminOverview"));
const AdminUsers = lazy(() => import("./pages/admin/AdminUsers"));
const AdminWorkgroups = lazy(() => import("./pages/admin/AdminWorkgroups"));
const AdminRuns = lazy(() => import("./pages/admin/AdminRuns"));
const AdminPricing = lazy(() => import("./pages/admin/AdminPricing"));

export function BootScreen({ label = "Opening your workspace" }: { label?: string }) {
  return (
    <div className="grid min-h-screen place-items-center bg-shell">
      <div className="flex flex-col items-center gap-5">
        <LogoMark size={44} />
        <div className="h-0.5 w-28 overflow-hidden rounded-full bg-ink/10">
          <div className="loader-bar h-full w-1/3 rounded-full bg-brand" />
        </div>
        <p className="text-[13px] text-ink-3">{label}…</p>
      </div>
    </div>
  );
}

function RequireManager({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <BootScreen />;
  if (status === "anonymous" || !user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  const location = useLocation();
  if (status === "loading") return <BootScreen />;
  if (status === "anonymous" || !user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  if (user.role !== "admin") return <Navigate to="/app" replace />;
  return <>{children}</>;
}

/** Pages that need a workgroup send first-time managers to the setup wizard. */
function RequireWorkgroup({ children }: { children: ReactNode }) {
  const { workgroup, loading } = useWorkgroups();
  if (loading) return <PageLoader />;
  if (!workgroup) return <Navigate to="/app/workgroups/new" replace />;
  return <>{children}</>;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { status, user } = useAuth();
  if (status === "loading") return <BootScreen label="Loading" />;
  if (user) return <Navigate to={user.role === "admin" ? "/admin" : "/app"} replace />;
  return <>{children}</>;
}

const wg = (node: ReactNode) => <RequireWorkgroup>{node}</RequireWorkgroup>;

export function App() {
  return (
    <Suspense fallback={<BootScreen label="Loading" />}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/join/:code" element={<Join />} />
        <Route path="/dev/checkout" element={<DevCheckout />} />
        <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
        <Route path="/signup" element={<GuestOnly><Signup /></GuestOnly>} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />

        <Route path="/app" element={<RequireManager><AppLayout /></RequireManager>}>
          <Route index element={wg(<Dashboard />)} />
          <Route path="workgroups/new" element={<NewWorkgroup />} />
          <Route path="staff" element={wg(<Staff />)} />
          <Route path="staff-ids" element={wg(<StaffIds />)} />
          <Route path="onboarding" element={wg(<Onboarding />)} />
          <Route path="roles" element={wg(<Roles />)} />
          <Route path="payroll" element={wg(<Payroll />)} />
          <Route path="payroll/runs/:runId" element={wg(<PayrollRun />)} />
          <Route path="wallet" element={wg(<Wallet />)} />
          <Route path="billing" element={wg(<Billing />)} />
          <Route path="analytics" element={wg(<Analytics />)} />
          <Route path="activity" element={wg(<Activity />)} />
          <Route path="notifications" element={<Notifications />} />
          <Route path="assistant" element={<Assistant />} />
          <Route path="settings" element={<Settings />} />
          <Route path="payments/callback" element={<PaymentCallback />} />
        </Route>

        <Route path="/admin" element={<RequireAdmin><AdminLayout /></RequireAdmin>}>
          <Route index element={<AdminOverview />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="workgroups" element={<AdminWorkgroups />} />
          <Route path="payroll" element={<AdminRuns />} />
          <Route path="pricing" element={<AdminPricing />} />
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
