"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import { Button, Card, ErrorNote, Field, Input } from "@/components/ui";

export default function OnboardingPage() {
  const api = useApi();
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createCompany(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/onboarding", { company_name: companyName });
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBusy(false);
    }
  }

  async function joinViaInvite() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/join");
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <p className="text-2xl font-bold tracking-tight">
          Thesa<span className="text-accent">.</span>
        </p>
        <p className="mt-1 text-sm text-muted">Let&apos;s get you set up</p>
      </div>

      <div className="grid w-full max-w-3xl gap-4 md:grid-cols-2">
        <Card>
          <h2 className="font-semibold">Create a company</h2>
          <p className="mt-1 text-sm text-muted">
            Start fresh — you&apos;ll be the owner.
          </p>
          <form onSubmit={createCompany} className="mt-4 space-y-3">
            <Field label="Company name">
              <Input
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Acme Concrete LLC"
                required
                maxLength={200}
              />
            </Field>
            <Button type="submit" disabled={busy || !companyName.trim()}>
              Create company
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="font-semibold">Join your team</h2>
          <p className="mt-1 text-sm text-muted">
            If someone invited the email on your account, one click connects
            you.
          </p>
          <div className="mt-4">
            <Button variant="ghost" onClick={joinViaInvite} disabled={busy}>
              Join via invite
            </Button>
          </div>
        </Card>
      </div>

      <div className="w-full max-w-3xl">
        <ErrorNote message={error} />
      </div>
    </main>
  );
}
