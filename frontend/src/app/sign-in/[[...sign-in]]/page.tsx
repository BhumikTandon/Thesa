import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <p className="text-2xl font-bold tracking-tight">
          Thesa<span className="text-accent">.</span>
        </p>
        <p className="mt-1 text-sm text-muted">
          Spend management for field workforces
        </p>
      </div>
      <SignIn />
    </main>
  );
}
