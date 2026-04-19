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
          <div className="hidden items-center gap-4 md:flex">
            <NavLink to="/research" className={navLinkClass}>
              Research
            </NavLink>
            <NavLink to="/journal" className={navLinkClass}>
              Journal
            </NavLink>
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
              <NavLink to="/research" className={mobileNavLinkClass}>
                Research
              </NavLink>
              <NavLink to="/journal" className={mobileNavLinkClass}>
                Journal
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

      <footer className="mt-16 border-t border-outline-variant bg-surface-container-lowest">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-6 py-6 text-sm text-on-surface-dim md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2">
            <span className="font-display tracking-tight">
              <span className="text-on-surface">SKLD</span>
              <span className="text-primary">.run</span>
            </span>
            <span className="font-mono text-[0.6875rem] uppercase tracking-wider">
              Skill Kinetics through Layered Darwinism
            </span>
          </div>
          <nav className="flex flex-wrap items-center gap-4">
            <a
              href="https://github.com/ty13r/skillforge"
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1.5 transition-colors hover:text-on-surface"
              aria-label="SKLD on GitHub"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden
                className="h-4 w-4"
              >
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.475 2 2 6.475 2 12a9.994 9.994 0 006.838 9.488c.5.087.687-.213.687-.476 0-.237-.013-1.024-.013-1.862-2.512.463-3.162-.612-3.362-1.175-.113-.288-.6-1.175-1.025-1.413-.35-.187-.85-.65-.013-.662.788-.013 1.35.725 1.538 1.025.9 1.512 2.338 1.087 2.912.825.088-.65.35-1.087.638-1.337-2.225-.25-4.55-1.113-4.55-4.938 0-1.088.387-1.987 1.025-2.688-.1-.25-.45-1.275.1-2.65 0 0 .837-.262 2.75 1.026a9.28 9.28 0 012.5-.338c.85 0 1.7.112 2.5.337 1.913-1.3 2.75-1.024 2.75-1.024.55 1.375.2 2.4.1 2.65.637.7 1.025 1.587 1.025 2.687 0 3.838-2.337 4.688-4.562 4.938.362.312.675.912.675 1.85 0 1.337-.013 2.412-.013 2.75 0 .262.188.574.688.474A10.005 10.005 0 0022 12c0-5.525-4.475-10-10-10z"
                />
              </svg>
              GitHub
            </a>
            <a href="/llms.txt" className="transition-colors hover:text-on-surface">
              /llms.txt
            </a>
            <Link to="/research" className="transition-colors hover:text-on-surface">
              Research
            </Link>
            <Link to="/journal" className="transition-colors hover:text-on-surface">
              Journal
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
