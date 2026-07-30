"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { UserButton } from "@clerk/nextjs";
import { MeProvider, useMe } from "@/components/me-context";
import { ROLE_LABELS } from "@/lib/format";

const NAV = [
  { href: "/dashboard", label: "Overview" },
  { href: "/router", label: "Reward Router" },
  { href: "/transactions", label: "Transactions" },
  { href: "/budgets", label: "Budgets" },
  { href: "/cards", label: "Card Portfolio" },
  { href: "/team", label: "Team" },
];

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const me = useMe();

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 flex w-56 flex-col border-r border-line bg-surface">
        <div className="px-5 py-5">
          <p className="text-lg font-bold tracking-tight">
            Thesa<span className="text-accent">.</span>
          </p>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`block rounded-lg px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-surface-2 font-medium text-accent"
                    : "text-muted hover:bg-surface-2 hover:text-foreground"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 border-t border-line px-5 py-4">
          <UserButton />
          <span className="text-xs text-muted">{ROLE_LABELS[me.role]}</span>
        </div>
      </aside>
      <main className="ml-56 flex-1 px-8 py-8">
        <div className="mx-auto max-w-5xl">{children}</div>
      </main>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <MeProvider>
      <Shell>{children}</Shell>
    </MeProvider>
  );
}
