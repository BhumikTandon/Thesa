"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
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
  Table,
} from "@/components/ui";
import {
  CATEGORY_LABELS,
  dollarsToCents,
  money,
  shortDate,
} from "@/lib/format";
import type { Budget, PortfolioCard, Transaction } from "@/lib/types";

export default function TransactionsPage() {
  const api = useApi();
  const [transactions, setTransactions] = useState<Transaction[] | null>(null);
  const [cards, setCards] = useState<PortfolioCard[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredOn, setOccurredOn] = useState(
    new Date().toISOString().slice(0, 10),
  );
  const [cardId, setCardId] = useState("");
  const [budgetId, setBudgetId] = useState("");

  const load = useCallback(() => {
    api.get<Transaction[]>("/transactions?limit=100").then(setTransactions);
    api.get<PortfolioCard[]>("/portfolio-cards").then(setCards);
    api.get<Budget[]>("/budgets").then(setBudgets);
  }, [api]);

  useEffect(load, [load]);

  if (!transactions) return <Spinner />;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const cents = dollarsToCents(amount);
    if (cents === null) {
      setError("Enter a valid amount");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/transactions", {
        merchant_name: merchant,
        amount_cents: cents,
        occurred_on: occurredOn,
        ...(cardId ? { portfolio_card_id: cardId } : {}),
        ...(budgetId ? { budget_id: budgetId } : {}),
      });
      setMerchant("");
      setAmount("");
      setCardId("");
      setBudgetId("");
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const cardLabel = (id: string | null) =>
    cards.find((c) => c.id === id)?.label ?? "—";

  return (
    <>
      <PageHeader
        title="Transactions"
        subtitle="Purchases feed the Reward Router's vendor analysis"
        action={
          <Button onClick={() => setShowForm((v) => !v)} variant="ghost">
            {showForm ? "Close" : "Record transaction"}
          </Button>
        }
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
            <Field label="Merchant">
              <Input
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                placeholder="Shell Oil #4421"
                required
                maxLength={200}
              />
            </Field>
            <Field label="Amount (USD)">
              <Input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="125.00"
                inputMode="decimal"
                required
              />
            </Field>
            <Field label="Date">
              <Input
                type="date"
                value={occurredOn}
                onChange={(e) => setOccurredOn(e.target.value)}
                required
              />
            </Field>
            <Field label="Card used (optional)">
              <Select value={cardId} onChange={(e) => setCardId(e.target.value)}>
                <option value="">Not on a registered card</option>
                {cards
                  .filter((c) => c.active)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.label} ·· {c.last4}
                    </option>
                  ))}
              </Select>
            </Field>
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
            <div className="flex items-end gap-3">
              <Button type="submit" disabled={busy}>
                Save
              </Button>
            </div>
          </form>
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        </Card>
      )}

      {transactions.length === 0 ? (
        <EmptyState
          title="No transactions yet"
          hint="Record purchases so the router can find rewards you're leaving on the table."
        />
      ) : (
        <Table headers={["Merchant", "Category", "Card", "Date", "Amount"]}>
          {transactions.map((t) => (
            <tr key={t.id}>
              <td className="px-4 py-3">{t.merchant_name}</td>
              <td className="px-4 py-3">
                <Badge>{CATEGORY_LABELS[t.category]}</Badge>
              </td>
              <td className="px-4 py-3 text-muted">
                {cardLabel(t.portfolio_card_id)}
              </td>
              <td className="px-4 py-3 text-muted">
                {shortDate(t.occurred_on)}
              </td>
              <td className="px-4 py-3 tabular-nums">
                {money(t.amount_cents)}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
