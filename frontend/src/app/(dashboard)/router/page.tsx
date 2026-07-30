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
  PageHeader,
  Spinner,
  StatCard,
  Table,
} from "@/components/ui";
import { CATEGORY_LABELS, money, pct, shortDate } from "@/lib/format";
import type {
  Recommendation,
  RewardsLedger,
  RoutingDecision,
} from "@/lib/types";

export default function RouterPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [ledger, setLedger] = useState<RewardsLedger | null>(null);
  const [decisions, setDecisions] = useState<RoutingDecision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyVendor, setBusyVendor] = useState<string | null>(null);

  const load = useCallback(() => {
    api.get<Recommendation[]>("/routing/recommendations").then(setRecs);
    api.get<RewardsLedger>("/routing/ledger").then(setLedger);
    api.get<RoutingDecision[]>("/routing/decisions").then(setDecisions);
  }, [api]);

  useEffect(() => {
    if (isManager) load();
  }, [isManager, load]);

  if (!isManager) {
    return (
      <EmptyState
        title="Managers only"
        hint="Reward routing is available to owners and office managers."
      />
    );
  }
  if (!recs || !ledger || !decisions) return <Spinner />;

  async function decide(rec: Recommendation, status: "accepted" | "dismissed") {
    setBusyVendor(rec.vendor_name);
    setError(null);
    try {
      await api.post("/routing/decisions", {
        vendor_name: rec.vendor_name,
        recommended_card_id: rec.recommended_card_id,
        status,
      });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusyVendor(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Reward Router"
        subtitle="Route each vendor's spend to the card that earns the most"
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Est. uplift / mo"
          value={money(ledger.est_monthly_uplift_cents)}
          accent
        />
        <StatCard
          label="Est. uplift / yr"
          value={money(ledger.est_annual_uplift_cents)}
          accent
        />
        <StatCard
          label="Accepted routings"
          value={String(ledger.accepted_decisions)}
        />
      </div>

      <div className="mt-6">
        <ErrorNote message={error} />
      </div>

      <h2 className="mb-3 mt-6 text-sm font-semibold">Recommendations</h2>
      {recs.length === 0 ? (
        <EmptyState
          title="No routing opportunities right now"
          hint="Add portfolio cards with reward rules and record transactions — the router finds vendors earning less than they could."
        />
      ) : (
        <div className="space-y-3">
          {recs.map((rec) => (
            <Card key={rec.vendor_name}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{rec.vendor_name}</p>
                    <Badge>{CATEGORY_LABELS[rec.category]}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-muted">
                    ~{money(rec.est_monthly_spend_cents)}/mo · currently
                    earning {pct(rec.current_reward_pct)} → route to{" "}
                    <span className="text-foreground">
                      {rec.recommended_card_label}
                    </span>{" "}
                    at {pct(rec.recommended_reward_pct)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <p className="text-right">
                    <span className="block text-lg font-semibold tabular-nums text-accent">
                      +{money(rec.est_monthly_uplift_cents)}/mo
                    </span>
                  </p>
                  <Button
                    onClick={() => decide(rec, "accepted")}
                    disabled={busyVendor === rec.vendor_name}
                  >
                    Accept
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => decide(rec, "dismissed")}
                    disabled={busyVendor === rec.vendor_name}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {decisions.length > 0 && (
        <>
          <h2 className="mb-3 mt-8 text-sm font-semibold">Decision history</h2>
          <Table headers={["Vendor", "Category", "Status", "Uplift / mo", "When"]}>
            {decisions.map((d) => (
              <tr key={d.id}>
                <td className="px-4 py-3">{d.vendor_name}</td>
                <td className="px-4 py-3">
                  <Badge>{CATEGORY_LABELS[d.category]}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge tone={d.status === "accepted" ? "green" : "gray"}>
                    {d.status}
                  </Badge>
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {money(d.est_monthly_uplift_cents)}
                </td>
                <td className="px-4 py-3 text-muted">
                  {shortDate(d.created_at)}
                </td>
              </tr>
            ))}
          </Table>
        </>
      )}
    </>
  );
}
