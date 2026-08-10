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
  Spinner,
} from "@/components/ui";
import { CATEGORY_LABELS, dollarsToCents, money } from "@/lib/format";
import type { SpendCategory, SpendPolicy } from "@/lib/types";

const ALL_CATEGORIES = Object.keys(CATEGORY_LABELS) as SpendCategory[];

export default function PoliciesPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [policies, setPolicies] = useState<SpendPolicy[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [denied, setDenied] = useState<SpendCategory[]>([]);
  const [maxAmount, setMaxAmount] = useState("");

  const load = useCallback(() => {
    api.get<SpendPolicy[]>("/spend-policies").then(setPolicies);
  }, [api]);

  useEffect(load, [load]);

  if (!policies) return <Spinner />;

  function toggleCategory(category: SpendCategory) {
    setDenied((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category],
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const maxCents = maxAmount ? dollarsToCents(maxAmount) : null;
    if (maxAmount && maxCents === null) {
      setError("Enter a valid max transaction amount");
      setBusy(false);
      return;
    }
    try {
      await api.post("/spend-policies", {
        name,
        denied_categories: denied,
        ...(maxCents !== null ? { max_transaction_cents: maxCents } : {}),
      });
      setName("");
      setDenied([]);
      setMaxAmount("");
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(policy: SpendPolicy) {
    await api.patch(`/spend-policies/${policy.id}`, { active: !policy.active });
    load();
  }

  if (!isManager) {
    return (
      <>
        <PageHeader
          title="Spend Policies"
          subtitle="Company rules enforced by the Card Teller at authorization time"
        />
        {policies.length === 0 ? (
          <EmptyState title="No spend policies" />
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {policies
              .filter((p) => p.active)
              .map((p) => (
                <PolicyCard key={p.id} policy={p} />
              ))}
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Spend Policies"
        subtitle="Deny categories and cap transaction size — Card Teller enforces these fail-closed"
        action={
          <Button onClick={() => setShowForm((v) => !v)} variant="ghost">
            {showForm ? "Close" : "New policy"}
          </Button>
        }
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Name">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Block travel & luxury"
                required
                maxLength={200}
              />
            </Field>
            <div>
              <p className="mb-2 text-xs font-medium text-muted">
                Denied categories
              </p>
              <div className="flex flex-wrap gap-2">
                {ALL_CATEGORIES.map((c) => {
                  const on = denied.includes(c);
                  return (
                    <button
                      key={c}
                      type="button"
                      onClick={() => toggleCategory(c)}
                      className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
                        on
                          ? "border-red-400/40 bg-red-400/10 text-red-400"
                          : "border-line text-muted hover:bg-surface-2"
                      }`}
                    >
                      {CATEGORY_LABELS[c]}
                    </button>
                  );
                })}
              </div>
            </div>
            <Field label="Max transaction USD (optional)">
              <Input
                value={maxAmount}
                onChange={(e) => setMaxAmount(e.target.value)}
                placeholder="500.00"
                inputMode="decimal"
                className="max-w-xs"
              />
            </Field>
            <Button type="submit" disabled={busy || !name.trim()}>
              Create policy
            </Button>
          </form>
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        </Card>
      )}

      {policies.length === 0 ? (
        <EmptyState
          title="No policies yet"
          hint='Example: deny "travel" company-wide, or cap any swipe at $500.'
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {policies.map((p) => (
            <PolicyCard
              key={p.id}
              policy={p}
              action={
                <Button variant="ghost" onClick={() => toggleActive(p)}>
                  {p.active ? "Deactivate" : "Activate"}
                </Button>
              }
            />
          ))}
        </div>
      )}
    </>
  );
}

function PolicyCard({
  policy,
  action,
}: {
  policy: SpendPolicy;
  action?: React.ReactNode;
}) {
  return (
    <Card className={policy.active ? "" : "opacity-50"}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="font-medium">{policy.name}</p>
          {!policy.active && <Badge tone="amber">inactive</Badge>}
        </div>
        {action}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {policy.max_transaction_cents != null && (
          <Badge tone="gray">
            Max {money(policy.max_transaction_cents)}/tx
          </Badge>
        )}
        {policy.denied_categories.length === 0 &&
          policy.max_transaction_cents == null && (
            <Badge tone="gray">No restrictions</Badge>
          )}
        {policy.denied_categories.map((c) => (
          <Badge key={c} tone="red">
            Deny {CATEGORY_LABELS[c]}
          </Badge>
        ))}
      </div>
    </Card>
  );
}
