export function money(cents: number): string {
  return (cents / 100).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
  });
}

export function pct(value: string | number): string {
  return `${Number(value).toFixed(2).replace(/\.?0+$/, "")}%`;
}

export function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function dollarsToCents(input: string): number | null {
  const value = Number(input);
  if (!Number.isFinite(value) || value <= 0) return null;
  return Math.round(value * 100);
}

export const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  office_manager: "Office manager",
  crew_lead: "Crew lead",
};

export const CATEGORY_LABELS: Record<string, string> = {
  fuel: "Fuel",
  lodging: "Lodging",
  materials: "Materials",
  food: "Food",
  travel: "Travel",
  other: "Other",
};
