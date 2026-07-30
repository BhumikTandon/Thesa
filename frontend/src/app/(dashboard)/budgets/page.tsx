"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useIsManager } from "@/components/me-context";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { CATEGORY_LABELS, dollarsToCents, money } from "@/lib/format";
import type { Budget } from "@/lib/types";

export default function BudgetsPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [budgets, setBudgets] = useState<Budget[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [limit, setLimit] = useState("");
  const [category, setCategory] = useState("");

  const load = useCallback(() => {
    api.get<Budget[]>("/budgets").then(setBudgets);
  }, [api]);

  useEffect(load, [load]);

  if (!budgets) return <Spinner />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const cents = dollarsToCents(limit);
    if (cents === null) {
      setError("Enter a valid limit");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/budgets", {
        name,
        limit_cents: cents,
        ...(category ? { category } : {}),
      });
      setName("");
      setLimit("");
      setCategory("");
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(budget: Budget) {
    await api.patch(`/budgets/${budget.id}`, { active: !budget.active });
    load();
  }

  return (
    <>
      <PageHeader
        title="Budgets"
        subtitle="Monthly envelopes per job site or department"
        action={
          isManager ? (
            <Button onClick={() => setShowForm((v) => !v)} variant="ghost">
              {showForm ? "Close" : "New budget"}
            </Button>
          ) : undefined
        }
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-3">
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Henderson job site"
                required
                maxLength={200}
              />
            </Field>
            <Field label="Monthly limit (USD)">
              <Input
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="10000"
                inputMode="decimal"
                required
              />
            </Field>
            <Field label="Category (optional)">
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">All categories</option>
                {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="sm:col-span-3">
              <Button type="submit" disabled={busy}>
                Create budget
              </Button>
            </div>
          </form>
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        </Card>
      )}

      {budgets.length === 0 ? (
        <EmptyState
          title="No budgets yet"
          hint='Create one, e.g. "$10,000/mo for the Henderson job site".'
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {budgets.map((b) => {
            const used = Math.min(
              100,
              Math.round((b.spent_cents_this_month / b.limit_cents) * 100),
            );
            return (
              <Card key={b.id} className={b.active ? "" : "opacity-50"}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium">{b.name}</p>
                    <div className="mt-1 flex items-center gap-2">
                      {b.category && (
                        <Badge>{CATEGORY_LABELS[b.category]}</Badge>
                      )}
                      {!b.active && <Badge tone="amber">inactive</Badge>}
                    </div>
                  </div>
                  {isManager && (
                    <Button variant="ghost" onClick={() => toggle(b)}>
                      {b.active ? "Deactivate" : "Activate"}
                    </Button>
                  )}
                </div>
                <div className="mt-4">
                  <div className="mb-1.5 flex justify-between text-sm">
                    <span className="text-muted">
                      {money(b.spent_cents_this_month)} spent
                    </span>
                    <span className="tabular-nums text-muted">
                      {money(b.remaining_cents)} left of {money(b.limit_cents)}
                    </span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-surface-2">
                    <div
                      className={`h-full rounded-full ${used > 90 ? "bg-red-400" : "bg-accent-dim"}`}
                      style={{ width: `${used}%` }}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
