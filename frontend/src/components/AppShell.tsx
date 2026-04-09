import { Link, NavLink, Outlet } from "react-router-dom";

import PrimaryButton from "./PrimaryButton";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  "text-sm font-medium transition-colors " +
  (isActive ? "text-on-surface" : "text-on-surface-dim hover:text-on-surface");

export default function AppShell() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-outline-variant bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="font-display text-xl tracking-tight">
              <span className="text-on-surface">SKLD</span>
              <span className="text-primary">.run</span>
            </span>
          </Link>

          <nav className="flex items-center gap-8">
            <NavLink to="/" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/registry" className={navLinkClass}>
              Registry
            </NavLink>
            <NavLink to="/bible" className={navLinkClass}>
              Bible
            </NavLink>
          </nav>

          <Link to="/new">
            <PrimaryButton type="button">+ New Evolution</PrimaryButton>
          </Link>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
