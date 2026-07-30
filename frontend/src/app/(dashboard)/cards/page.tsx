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
import { CATEGORY_LABELS, pct } from "@/lib/format";
import type { PortfolioCard, SpendCategory } from "@/lib/types";

interface RuleDraft {
  category: SpendCategory;
  reward_pct: string;
}

export default function CardsPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [cards, setCards] = useState<PortfolioCard[] | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [label, setLabel] = useState("");
  const [issuer, setIssuer] = useState("");
  const [last4, setLast4] = useState("");
  const [defaultPct, setDefaultPct] = useState("1.00");
  const [rules, setRules] = useState<RuleDraft[]>([]);

  const load = useCallback(() => {
    api.get<PortfolioCard[]>("/portfolio-cards").then(setCards);
  }, [api]);

  useEffect(load, [load]);

  if (!cards) return <Spinner />;

  function addRule() {
    const used = new Set(rules.map((r) => r.category));
    const next = (
      Object.keys(CATEGORY_LABELS) as SpendCategory[]
    ).find((c) => !used.has(c));
    if (next) setRules([...rules, { category: next, reward_pct: "3.00" }]);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/portfolio-cards", {
        label,
        issuer,
        last4,
        default_reward_pct: defaultPct,
        rules,
      });
      setLabel("");
      setIssuer("");
      setLast4("");
      setDefaultPct("1.00");
      setRules([]);
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(card: PortfolioCard) {
    await api.patch(`/portfolio-cards/${card.id}`, { active: !card.active });
    load();
  }

  return (
    <>
      <PageHeader
        title="Card Portfolio"
        subtitle="The corporate cards you already have — Thesa routes spend across them"
        action={
          isManager ? (
            <Button onClick={() => setShowForm((v) => !v)} variant="ghost">
              {showForm ? "Close" : "Register card"}
            </Button>
          ) : undefined
        }
      />

      {showForm && (
        <Card className="mb-6">
          <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-4">
              <Field label="Label">
                <Input
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="Chase Ink Business"
                  required
                  maxLength={100}
                />
              </Field>
              <Field label="Issuer">
                <Input
                  value={issuer}
                  onChange={(e) => setIssuer(e.target.value)}
                  placeholder="Chase"
                  required
                  maxLength={100}
                />
              </Field>
              <Field label="Last 4 digits">
                <Input
                  value={last4}
                  onChange={(e) => setLast4(e.target.value)}
                  placeholder="4421"
                  pattern="\d{4}"
                  required
                />
              </Field>
              <Field label="Base % back">
                <Input
                  value={defaultPct}
                  onChange={(e) => setDefaultPct(e.target.value)}
                  inputMode="decimal"
                  required
                />
              </Field>
            </div>

            <div>
              <p className="mb-2 text-xs font-medium text-muted">
                Category bonuses
              </p>
              <div className="space-y-2">
                {rules.map((rule, i) => (
                  <div key={rule.category} className="flex items-center gap-2">
                    <Select
                      value={rule.category}
                      onChange={(e) => {
                        const next = [...rules];
                        next[i] = {
                          ...rule,
                          category: e.target.value as SpendCategory,
                        };
                        setRules(next);
                      }}
                      className="max-w-44"
                    >
                      {Object.entries(CATEGORY_LABELS).map(
                        ([value, categoryLabel]) => (
                          <option key={value} value={value}>
                            {categoryLabel}
                          </option>
                        ),
                      )}
                    </Select>
                    <Input
                      value={rule.reward_pct}
                      onChange={(e) => {
                        const next = [...rules];
                        next[i] = { ...rule, reward_pct: e.target.value };
                        setRules(next);
                      }}
                      inputMode="decimal"
                      className="max-w-24"
                    />
                    <span className="text-sm text-muted">% back</span>
                    <Button
                      variant="ghost"
                      onClick={() => setRules(rules.filter((_, j) => j !== i))}
                    >
                      Remove
                    </Button>
                  </div>
                ))}
              </div>
              <div className="mt-2">
                <Button variant="ghost" onClick={addRule}>
                  Add category bonus
                </Button>
              </div>
            </div>

            <Button type="submit" disabled={busy}>
              Register card
            </Button>
          </form>
          <div className="mt-3">
            <ErrorNote message={error} />
          </div>
        </Card>
      )}

      {cards.length === 0 ? (
        <EmptyState
          title="No cards registered"
          hint="Register the corporate cards you already carry, with their reward categories, so the router can optimize across them."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {cards.map((card) => (
            <Card key={card.id} className={card.active ? "" : "opacity-50"}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{card.label}</p>
                  <p className="mt-0.5 text-sm text-muted">
                    {card.issuer} ···· {card.last4}
                  </p>
                </div>
                {isManager && (
                  <Button variant="ghost" onClick={() => toggle(card)}>
                    {card.active ? "Deactivate" : "Activate"}
                  </Button>
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Badge tone="gray">
                  {pct(card.default_reward_pct)} everywhere
                </Badge>
                {card.rules.map((rule) => (
                  <Badge key={rule.id} tone="green">
                    {pct(rule.reward_pct)} {CATEGORY_LABELS[rule.category]}
                  </Badge>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
