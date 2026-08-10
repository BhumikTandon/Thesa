"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useIsManager, useMe } from "@/components/me-context";
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
import {
  CATEGORY_LABELS,
  dollarsToCents,
  money,
  shortDate,
} from "@/lib/format";
import type {
  Budget,
  IssuedCard,
  IssuedCardStatus,
  Member,
  SpendCategory,
} from "@/lib/types";

export default function IssuedCardsPage() {
  const api = useApi();
  const me = useMe();
  const isManager = useIsManager();
  const [cards, setCards] = useState<IssuedCard[] | null>(null);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [label, setLabel] = useState("");
  const [userId, setUserId] = useState("");
  const [budgetId, setBudgetId] = useState("");
  const [vendor, setVendor] = useState("");
  const [category, setCategory] = useState("");
  const [limit, setLimit] = useState("");

  const load = useCallback(() => {
    api.get<IssuedCard[]>("/issued-cards").then(setCards);
    api.get<Budget[]>("/budgets").then(setBudgets);
    if (isManager) {
      api.get<Member[]>("/team/members").then(setMembers);
    }
  }, [api, isManager]);

  useEffect(load, [load]);

  if (!cards) return <Spinner />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    const limitCents = limit ? dollarsToCents(limit) : null;
    if (limit && limitCents === null) {
      setError("Enter a valid single-transaction limit");
      setBusy(false);
      return;
    }
    try {
      await api.post("/issued-cards", {
        label,
        ...(isManager && userId ? { user_id: userId } : {}),
        ...(budgetId ? { budget_id: budgetId } : {}),
        ...(vendor.trim() ? { scoped_vendor: vendor.trim() } : {}),
        ...(category ? { scoped_category: category } : {}),
        ...(limitCents !== null ? { single_tx_limit_cents: limitCents } : {}),
      });
      setLabel("");
      setUserId("");
      setBudgetId("");
      setVendor("");
      setCategory("");
      setLimit("");
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(card: IssuedCard, status: IssuedCardStatus) {
    setError(null);
    try {
      await api.patch(`/issued-cards/${card.id}`, { status });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  }

  const memberLabel = (id: string) => {
    const m = members.find((x) => x.id === id);
    if (id === me.user_id) return "you";
    return m?.email ?? id.slice(0, 8);
  };

  const budgetLabel = (id: string | null) =>
    budgets.find((b) => b.id === id)?.name ?? "—";

  return (
    <>
      <PageHeader
        title="Issued Cards"
        subtitle="Scoped virtual cards for field spend (stub issuer until Marqeta)"
        action={
          <Button onClick={() => setShowForm((v) => !v)} variant="ghost">
            {showForm ? "Close" : "Request card"}
          </Button>
        }
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
            <Field label="Label">
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Shell — Henderson site"
                required
                maxLength={200}
              />
            </Field>
            {isManager && (
              <Field label="Assign to">
                <Select
                  value={userId}
                  onChange={(e) => setUserId(e.target.value)}
                >
                  <option value="">Yourself</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.email ?? m.id.slice(0, 8)}
                      {m.id === me.user_id ? " (you)" : ""}
                    </option>
                  ))}
                </Select>
              </Field>
            )}
            <Field label="Budget (optional)">
              <Select
                value={budgetId}
                onChange={(e) => setBudgetId(e.target.value)}
              >
                <option value="">No budget</option>
                {budgets
                  .filter((b) => b.active)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
              </Select>
            </Field>
            <Field label="Vendor scope (optional)">
              <Input
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
                placeholder="Shell"
                maxLength={200}
              />
            </Field>
            <Field label="Category scope (optional)">
              <Select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">Any category</option>
                {Object.entries(CATEGORY_LABELS).map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Single-tx limit USD (optional)">
              <Input
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="100.00"
                inputMode="decimal"
              />
            </Field>
            <div className="sm:col-span-2">
              <Button type="submit" disabled={busy || !label.trim()}>
                Provision card
              </Button>
            </div>
          </form>
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        </Card>
      )}

      {!showForm && <div className="mb-4"><ErrorNote message={error} /></div>}

      {cards.length === 0 ? (
        <EmptyState
          title="No issued cards yet"
          hint="Request a scoped virtual card for a vendor or job site. The Card Teller enforces limits at authorization time."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cards.map((card) => (
            <Card
              key={card.id}
              className={
                card.status === "active"
                  ? ""
                  : card.status === "frozen"
                    ? "opacity-80"
                    : "opacity-50"
              }
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{card.label}</p>
                  <p className="mt-0.5 text-sm text-muted">
                    ···· {card.last4}
                    {isManager && (
                      <> · {memberLabel(card.user_id)}</>
                    )}
                  </p>
                </div>
                <Badge
                  tone={
                    card.status === "active"
                      ? "green"
                      : card.status === "frozen"
                        ? "amber"
                        : "gray"
                  }
                >
                  {card.status}
                </Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {card.scoped_vendor && (
                  <Badge>Vendor: {card.scoped_vendor}</Badge>
                )}
                {card.scoped_category && (
                  <Badge>
                    {CATEGORY_LABELS[card.scoped_category as SpendCategory]}
                  </Badge>
                )}
                {card.single_tx_limit_cents != null && (
                  <Badge tone="gray">
                    Max {money(card.single_tx_limit_cents)}/tx
                  </Badge>
                )}
                {card.budget_id && (
                  <Badge tone="gray">{budgetLabel(card.budget_id)}</Badge>
                )}
              </div>
              <p className="mt-3 text-xs text-muted">
                Issued {shortDate(card.created_at)}
              </p>
              {isManager && card.status !== "canceled" && (
                <div className="mt-4 flex gap-2">
                  {card.status === "active" && (
                    <Button
                      variant="ghost"
                      onClick={() => setStatus(card, "frozen")}
                    >
                      Freeze
                    </Button>
                  )}
                  {card.status === "frozen" && (
                    <Button
                      variant="ghost"
                      onClick={() => setStatus(card, "active")}
                    >
                      Unfreeze
                    </Button>
                  )}
                  <Button
                    variant="danger"
                    onClick={() => setStatus(card, "canceled")}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
