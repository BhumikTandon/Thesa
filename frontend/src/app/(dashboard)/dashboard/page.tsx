"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useIsManager } from "@/components/me-context";
import { Badge, Card, PageHeader, Spinner, StatCard } from "@/components/ui";
import { CATEGORY_LABELS, money, shortDate } from "@/lib/format";
import type {
  Budget,
  PerDiemStatus,
  RewardsLedger,
  Transaction,
} from "@/lib/types";

export default function DashboardPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [ledger, setLedger] = useState<RewardsLedger | null>(null);
  const [budgets, setBudgets] = useState<Budget[] | null>(null);
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [perDiem, setPerDiem] = useState<PerDiemStatus | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const loads: Promise<unknown>[] = [
      api.get<Budget[]>("/budgets").then(setBudgets),
      api.get<Transaction[]>("/transactions?limit=8").then(setTransactions),
      api.get<PerDiemStatus>("/per-diems/me").then(setPerDiem).catch(() => {}),
    ];
    if (isManager) {
      loads.push(api.get<RewardsLedger>("/routing/ledger").then(setLedger));
    }
    Promise.allSettled(loads).then(() => setLoaded(true));
  }, [api, isManager]);

  if (!loaded) return <Spinner />;

  const activeBudgets = (budgets ?? []).filter((b) => b.active);
  const totalLimit = activeBudgets.reduce((s, b) => s + b.limit_cents, 0);
  const totalSpent = activeBudgets.reduce(
    (s, b) => s + b.spent_cents_this_month,
    0,
  );

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Company spend and rewards at a glance"
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {ledger && (
          <StatCard
            label="Rewards uplift / yr"
            value={money(ledger.est_annual_uplift_cents)}
            hint={`${ledger.accepted_decisions} routing decision${ledger.accepted_decisions === 1 ? "" : "s"} accepted`}
            accent
          />
        )}
        <StatCard
          label="Spent this month"
          value={money(totalSpent)}
          hint={totalLimit ? `of ${money(totalLimit)} budgeted` : undefined}
        />
        <StatCard
          label="Active budgets"
          value={String(activeBudgets.length)}
        />
        {perDiem && (
          <StatCard
            label="Per diem left today"
            value={money(perDiem.remaining_today_cents)}
            hint={`of ${money(perDiem.daily_limit_cents)} daily`}
            accent
          />
        )}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Recent transactions</h2>
            <Link
              href="/transactions"
              className="text-xs text-accent hover:underline"
            >
              View all
            </Link>
          </div>
          {transactions && transactions.length > 0 ? (
            <ul className="space-y-2.5">
              {transactions.map((t) => (
                <li
                  key={t.id}
                  className="flex items-center justify-between gap-3 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate">{t.merchant_name}</p>
                    <p className="text-xs text-muted">
                      {shortDate(t.occurred_on)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge>{CATEGORY_LABELS[t.category]}</Badge>
                    <span className="tabular-nums">
                      {money(t.amount_cents)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted">No transactions yet.</p>
          )}
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Budgets</h2>
            <Link
              href="/budgets"
              className="text-xs text-accent hover:underline"
            >
              Manage
            </Link>
          </div>
          {activeBudgets.length > 0 ? (
            <ul className="space-y-4">
              {activeBudgets.slice(0, 5).map((b) => {
                const used = Math.min(
                  100,
                  Math.round((b.spent_cents_this_month / b.limit_cents) * 100),
                );
                return (
                  <li key={b.id}>
                    <div className="mb-1.5 flex justify-between text-sm">
                      <span>{b.name}</span>
                      <span className="tabular-nums text-muted">
                        {money(b.spent_cents_this_month)} /{" "}
                        {money(b.limit_cents)}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                      <div
                        className={`h-full rounded-full ${used > 90 ? "bg-red-400" : "bg-accent-dim"}`}
                        style={{ width: `${used}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="text-sm text-muted">No budgets yet.</p>
          )}
        </Card>
      </div>
    </>
  );
}
