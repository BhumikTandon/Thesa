"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useIsManager } from "@/components/me-context";
import {
  Badge,
  EmptyState,
  PageHeader,
  Spinner,
  Table,
} from "@/components/ui";
import { CATEGORY_LABELS, money, shortDate } from "@/lib/format";
import type { AuthorizationDecision } from "@/lib/types";

export default function AuthorizationsPage() {
  const api = useApi();
  const isManager = useIsManager();
  const [rows, setRows] = useState<AuthorizationDecision[] | null>(null);

  const load = useCallback(() => {
    if (!isManager) return;
    api.get<AuthorizationDecision[]>("/authorization-decisions").then(setRows);
  }, [api, isManager]);

  useEffect(load, [load]);

  if (!isManager) {
    return (
      <EmptyState
        title="Managers only"
        hint="Authorization history is available to owners and office managers."
      />
    );
  }

  if (!rows) return <Spinner />;

  const declined = rows.filter((r) => r.decision === "declined");

  return (
    <>
      <PageHeader
        title="Authorizations"
        subtitle="Card Teller approve/decline outcomes from JIT funding requests"
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-3">
        <Stat label="Total decisions" value={String(rows.length)} />
        <Stat label="Approved" value={String(rows.length - declined.length)} />
        <Stat label="Declined" value={String(declined.length)} accent />
      </div>

      {rows.length === 0 ? (
        <EmptyState
          title="No authorizations yet"
          hint="When a stub (or Marqeta) JIT webhook hits /webhooks/jit, decisions appear here."
        />
      ) : (
        <>
          {declined.length > 0 && (
            <>
              <h2 className="mb-3 text-sm font-semibold">
                Declined / out of policy
              </h2>
              <Table
                headers={[
                  "Merchant",
                  "Category",
                  "Amount",
                  "Reason",
                  "When",
                ]}
              >
                {declined.map((d) => (
                  <tr key={d.id}>
                    <td className="px-4 py-3">{d.merchant_name}</td>
                    <td className="px-4 py-3">
                      <Badge>{CATEGORY_LABELS[d.category]}</Badge>
                    </td>
                    <td className="px-4 py-3 tabular-nums">
                      {money(d.amount_cents)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone="red">{d.reason}</Badge>
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {shortDate(d.created_at)}
                    </td>
                  </tr>
                ))}
              </Table>
            </>
          )}

          <h2 className="mb-3 mt-8 text-sm font-semibold">All decisions</h2>
          <Table
            headers={[
              "Merchant",
              "Category",
              "Amount",
              "Decision",
              "Reason",
              "When",
            ]}
          >
            {rows.map((d) => (
              <tr key={d.id}>
                <td className="px-4 py-3">{d.merchant_name}</td>
                <td className="px-4 py-3">
                  <Badge>{CATEGORY_LABELS[d.category]}</Badge>
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {money(d.amount_cents)}
                </td>
                <td className="px-4 py-3">
                  <Badge tone={d.decision === "approved" ? "green" : "red"}>
                    {d.decision}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-muted">{d.reason}</td>
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

function Stat({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-muted">
        {label}
      </p>
      <p
        className={`mt-2 text-2xl font-semibold tabular-nums ${
          accent ? "text-accent" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
