import { Logo } from "../../components/Logo";
import { ButtonLink } from "../../components/ui";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col bg-shell px-5 py-6">
      <Logo />
      <div className="m-auto max-w-md text-center">
        <p className="num font-display text-[64px] font-semibold leading-none text-brand">404</p>
        <h1 className="mt-4 text-[28px] font-semibold">This page doesn't exist</h1>
        <p className="mt-2 text-[14px] leading-6 text-ink-2">The link may be old or mistyped. If a staff member sent you here, ask your finance team for the current registration link.</p>
        <div className="mt-6 flex justify-center gap-2">
          <ButtonLink to="/">Go home</ButtonLink>
          <ButtonLink to="/app" variant="secondary">Open dashboard</ButtonLink>
        </div>
      </div>
    </div>
  );
}
