"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { useIsManager, useMe } from "@/components/me-context";
import {
  Badge,
  Button,
  Card,
  ErrorNote,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
  Table,
} from "@/components/ui";
import {
  ROLE_LABELS,
  dollarsToCents,
  money,
  shortDate,
} from "@/lib/format";
import type { Invite, Member, PerDiem, Role } from "@/lib/types";

export default function TeamPage() {
  const api = useApi();
  const me = useMe();
  const isManager = useIsManager();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [perDiems, setPerDiems] = useState<PerDiem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("crew_lead");
  const [perDiemUser, setPerDiemUser] = useState("");
  const [perDiemAmount, setPerDiemAmount] = useState("");

  const load = useCallback(() => {
    api.get<Member[]>("/team/members").then(setMembers);
    if (isManager) {
      api.get<Invite[]>("/team/invites").then(setInvites);
      api.get<PerDiem[]>("/per-diems").then(setPerDiems);
    }
  }, [api, isManager]);

  useEffect(load, [load]);

  if (!members) return <Spinner />;

  async function invite(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/team/invites", { email, role });
      setEmail("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(inviteId: string) {
    await api.post(`/team/invites/${inviteId}/revoke`);
    load();
  }

  async function assignPerDiem(event: React.FormEvent) {
    event.preventDefault();
    const cents = dollarsToCents(perDiemAmount);
    if (cents === null || !perDiemUser) {
      setError("Pick a member and a valid daily amount");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.post("/per-diems", {
        user_id: perDiemUser,
        daily_limit_cents: cents,
      });
      setPerDiemUser("");
      setPerDiemAmount("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const perDiemFor = (userId: string) =>
    perDiems.find((p) => p.user_id === userId && p.active);

  return (
    <>
      <PageHeader title="Team" subtitle="Members, invites, and per diems" />

      {isManager && (
        <div className="mb-6 grid gap-4 md:grid-cols-2">
          <Card>
            <h2 className="mb-3 text-sm font-semibold">Invite someone</h2>
            <form onSubmit={invite} className="space-y-3">
              <Field label="Email">
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="foreman@acmeconcrete.com"
                  required
                />
              </Field>
              <Field label="Role">
                <Select
                  value={role}
                  onChange={(e) => setRole(e.target.value as Role)}
                >
                  <option value="crew_lead">Crew lead</option>
                  <option value="office_manager">Office manager</option>
                  {me.role === "owner" && (
                    <option value="owner">Owner</option>
                  )}
                </Select>
              </Field>
              <Button type="submit" disabled={busy}>
                Send invite
              </Button>
            </form>
          </Card>

          <Card>
            <h2 className="mb-3 text-sm font-semibold">Assign per diem</h2>
            <form onSubmit={assignPerDiem} className="space-y-3">
              <Field label="Member">
                <Select
                  value={perDiemUser}
                  onChange={(e) => setPerDiemUser(e.target.value)}
                >
                  <option value="">Choose a member</option>
                  {members.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.email ?? m.id.slice(0, 8)}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Daily allowance (USD)">
                <Input
                  value={perDiemAmount}
                  onChange={(e) => setPerDiemAmount(e.target.value)}
                  placeholder="150"
                  inputMode="decimal"
                />
              </Field>
              <Button type="submit" disabled={busy}>
                Assign
              </Button>
            </form>
          </Card>
        </div>
      )}

      <div className="mb-6">
        <ErrorNote message={error} />
      </div>

      <h2 className="mb-3 text-sm font-semibold">Members</h2>
      <Table headers={["Email", "Role", "Per diem", "Joined"]}>
        {members.map((m) => {
          const pd = perDiemFor(m.id);
          return (
            <tr key={m.id}>
              <td className="px-4 py-3">
                {m.email ?? <span className="text-muted">—</span>}
                {m.id === me.user_id && (
                  <span className="ml-2 text-xs text-accent">you</span>
                )}
              </td>
              <td className="px-4 py-3">
                <Badge tone={m.role === "owner" ? "green" : "gray"}>
                  {ROLE_LABELS[m.role]}
                </Badge>
              </td>
              <td className="px-4 py-3 tabular-nums text-muted">
                {pd ? `${money(pd.daily_limit_cents)}/day` : "—"}
              </td>
              <td className="px-4 py-3 text-muted">{shortDate(m.created_at)}</td>
            </tr>
          );
        })}
      </Table>

      {isManager && invites.length > 0 && (
        <>
          <h2 className="mb-3 mt-8 text-sm font-semibold">Invites</h2>
          <Table headers={["Email", "Role", "Status", "Sent", ""]}>
            {invites.map((inv) => (
              <tr key={inv.id}>
                <td className="px-4 py-3">{inv.email}</td>
                <td className="px-4 py-3">
                  <Badge>{ROLE_LABELS[inv.role]}</Badge>
                </td>
                <td className="px-4 py-3">
                  <Badge
                    tone={
                      inv.status === "pending"
                        ? "amber"
                        : inv.status === "accepted"
                          ? "green"
                          : "gray"
                    }
                  >
                    {inv.status}
                  </Badge>
                </td>
                <td className="px-4 py-3 text-muted">
                  {shortDate(inv.created_at)}
                </td>
                <td className="px-4 py-3 text-right">
                  {inv.status === "pending" && (
                    <Button variant="danger" onClick={() => revoke(inv.id)}>
                      Revoke
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </Table>
        </>
      )}
    </>
  );
}
