export type Role = "owner" | "office_manager" | "crew_lead";

export type SpendCategory =
  | "fuel"
  | "lodging"
  | "materials"
  | "food"
  | "travel"
  | "other";

export interface Me {
  user_id: string;
  company_id: string;
  clerk_user_id: string;
  role: Role;
}

export interface RewardRule {
  id: string;
  category: SpendCategory;
  reward_pct: string;
}

export interface PortfolioCard {
  id: string;
  label: string;
  issuer: string;
  last4: string;
  default_reward_pct: string;
  active: boolean;
  rules: RewardRule[];
  created_at: string;
}

export interface Budget {
  id: string;
  name: string;
  category: SpendCategory | null;
  limit_cents: number;
  active: boolean;
  spent_cents_this_month: number;
  remaining_cents: number;
  created_at: string;
}

export interface Transaction {
  id: string;
  user_id: string | null;
  portfolio_card_id: string | null;
  budget_id: string | null;
  merchant_name: string;
  category: SpendCategory;
  amount_cents: number;
  currency: string;
  occurred_on: string;
  created_at: string;
}

export interface Recommendation {
  vendor_name: string;
  category: SpendCategory;
  est_monthly_spend_cents: number;
  current_card_id: string | null;
  current_reward_pct: string;
  recommended_card_id: string;
  recommended_card_label: string;
  recommended_reward_pct: string;
  est_monthly_uplift_cents: number;
}

export interface RoutingDecision {
  id: string;
  vendor_name: string;
  category: SpendCategory;
  recommended_card_id: string;
  previous_card_id: string | null;
  status: "recommended" | "accepted" | "dismissed";
  est_monthly_spend_cents: number;
  est_monthly_uplift_cents: number;
  created_at: string;
}

export interface RewardsLedger {
  accepted_decisions: number;
  est_monthly_uplift_cents: number;
  est_annual_uplift_cents: number;
}

export interface Member {
  id: string;
  email: string | null;
  role: Role;
  created_at: string;
}

export interface Invite {
  id: string;
  email: string;
  role: Role;
  status: "pending" | "accepted" | "revoked";
  created_at: string;
}

export interface PerDiem {
  id: string;
  user_id: string;
  daily_limit_cents: number;
  active: boolean;
  created_at: string;
}

export interface PerDiemStatus {
  daily_limit_cents: number;
  spent_today_cents: number;
  remaining_today_cents: number;
}
