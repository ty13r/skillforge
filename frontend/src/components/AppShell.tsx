import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import PrimaryButton from "./PrimaryButton";
import ThemeToggle from "./ThemeToggle";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  "text-sm font-medium transition-colors " +
  (isActive ? "text-on-surface" : "text-on-surface-dim hover:text-on-surface");

const mobileNavLinkClass = ({ isActive }: { isActive: boolean }) =>
  "block rounded-lg px-4 py-3 text-base font-medium transition-colors " +
  (isActive
    ? "bg-surface-container-low text-on-surface"
    : "text-on-surface-dim hover:bg-surface-container-low hover:text-on-surface");

export default function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  // Close the mobile menu whenever the route changes.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  // Close on Escape for keyboard users.
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [menuOpen]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-outline-variant bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-3 px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2">
            <span className="font-display text-xl tracking-tight">
              <span className="text-on-surface">SKLD</span>
              <span className="text-primary">.run</span>
            </span>
          </Link>

          {/* Desktop nav — hidden below md */}
          <nav className="hidden items-center gap-8 md:flex">
            <NavLink to="/" end className={navLinkClass}>
              Dashboard
            </NavLink>
            <NavLink to="/registry" className={navLinkClass}>
              Registry
            </NavLink>
            <NavLink to="/bench" className={navLinkClass}>
              Bench
            </NavLink>
            <NavLink to="/taxonomy" className={navLinkClass}>
              Taxonomy
            </NavLink>
            <NavLink to="/bible" className={navLinkClass}>
              Bible
            </NavLink>
          </nav>

          {/* Desktop right cluster — hidden below md */}
          <div className="hidden items-center gap-3 md:flex">
            <ThemeToggle />
            <Link to="/new">
              <PrimaryButton type="button">+ New Evolution</PrimaryButton>
            </Link>
          </div>

          {/* Mobile right cluster — hidden at md and above */}
          <div className="flex items-center gap-2 md:hidden">
            <ThemeToggle />
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-label={menuOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={menuOpen}
              aria-controls="mobile-nav-drawer"
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-outline-variant bg-surface-container-low text-on-surface transition-colors hover:bg-surface-container"
            >
              {menuOpen ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                  className="h-5 w-5"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                  className="h-5 w-5"
                >
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile drawer — slides down below the header */}
        {menuOpen && (
          <div
            id="mobile-nav-drawer"
            className="border-t border-outline-variant bg-surface/95 backdrop-blur md:hidden"
          >
            <nav className="mx-auto flex max-w-[1400px] flex-col gap-1 px-4 py-3">
              <NavLink to="/" end className={mobileNavLinkClass}>
                Dashboard
              </NavLink>
              <NavLink to="/registry" className={mobileNavLinkClass}>
                Registry
              </NavLink>
              <NavLink to="/bench" className={mobileNavLinkClass}>
                Bench
              </NavLink>
              <NavLink to="/taxonomy" className={mobileNavLinkClass}>
                Taxonomy
              </NavLink>
              <NavLink to="/bible" className={mobileNavLinkClass}>
                Bible
              </NavLink>
              <div className="my-2 h-px bg-outline-variant" />
              <Link to="/new" className="block">
                <PrimaryButton type="button" className="w-full justify-center">
                  + New Evolution
                </PrimaryButton>
              </Link>
            </nav>
          </div>
        )}
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
