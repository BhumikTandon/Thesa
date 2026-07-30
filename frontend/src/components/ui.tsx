"use client";

import { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-line bg-surface p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
  accent = false,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: boolean;
}) {
  return (
    <Card>
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
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

const BADGE_STYLES: Record<string, string> = {
  green: "bg-accent/10 text-accent border-accent/20",
  gray: "bg-surface-2 text-muted border-line",
  red: "bg-red-400/10 text-red-400 border-red-400/20",
  amber: "bg-amber-400/10 text-amber-400 border-amber-400/20",
};

export function Badge({
  children,
  tone = "gray",
}: {
  children: ReactNode;
  tone?: keyof typeof BADGE_STYLES;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${BADGE_STYLES[tone]}`}
    >
      {children}
    </span>
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled = false,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
}) {
  const styles = {
    primary:
      "bg-accent-dim text-black font-semibold hover:bg-accent disabled:opacity-40",
    ghost:
      "border border-line text-foreground hover:bg-surface-2 disabled:opacity-40",
    danger:
      "border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-40",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3.5 py-2 text-sm transition-colors ${styles}`}
    >
      {children}
    </button>
  );
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none placeholder:text-muted/60 focus:border-accent/50 ${props.className ?? ""}`}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded-lg border border-line bg-surface-2 px-3 py-2 text-sm outline-none focus:border-accent/50 ${props.className ?? ""}`}
    />
  );
}

export function Field({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium text-muted">
        {label}
      </span>
      {children}
    </label>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" />
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-line py-12 text-center">
      <p className="text-sm font-medium text-muted">{title}</p>
      {hint && <p className="mt-1 text-xs text-muted/70">{hint}</p>}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="rounded-lg border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-400">
      {message}
    </p>
  );
}

export function Table({
  headers,
  children,
}: {
  headers: string[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-line">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line bg-surface text-left">
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-muted"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  );
}
