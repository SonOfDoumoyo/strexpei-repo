export type Paged<T> = { items: T[]; total: number; page: number; page_size: number };

export type User = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  phone: string | null;
  role: "manager" | "admin";
  status: string;
  verified: boolean;
  has_paid_plan: boolean;
  workgroup_count: number;
  preferences: Record<string, unknown>;
  created_at: string;
  last_login_at: string | null;
};

export type Plan = {
  code: string;
  name: string;
  tagline: string | null;
  min_staff: number;
  max_staff: number | null;
  base_fee_kobo: number;
  per_staff_kobo: number;
  ai_monthly_quota: number;
  features: string[];
  active: boolean;
  sort_order: number;
};

export type Subscription = {
  id: string;
  status: "trialing" | "active" | "past_due" | "expired" | "canceled";
  usable: boolean;
  plan: Plan;
  seats: number;
  billing_cycle: "monthly" | "annual";
  monthly_kobo: number;
  renewal_amount_kobo: number;
  trial_ends_at: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  ends_at: string | null;
  days_left: number | null;
  auto_renew: boolean;
};

export type Dva = { account_number: string; account_name: string | null; bank_name: string | null };

export type Workgroup = {
  id: string;
  name: string;
  address: string | null;
  industry: string | null;
  headcount: number;
  staff_id_prefix: string;
  invite_code: string;
  invite_active: boolean;
  join_url: string;
  payment_mode: "manual" | "automatic";
  payday_day: number;
  payday_time: string;
  timezone: string;
  next_payday_at: string | null;
  wallet_balance_kobo: number;
  dva: Dva | null;
  subscription_status: string | null;
  subscription?: Subscription | null;
  seats_in_use?: number;
  created_at: string;
};

export type AuditEntry = { id: string; action: string; summary: string; actor: string; created_at: string; meta: Record<string, unknown> };

export type RunSummary = {
  id: string;
  number: string;
  status: RunStatus;
  trigger: string;
  period_label: string;
  staff_count: number;
  total_kobo: number;
  salaries_kobo: number;
  paid_kobo: number;
  created_at: string;
  completed_at: string | null;
};

export type Overview = {
  workgroup: Workgroup;
  staff: {
    total: number;
    registered: number;
    pending: number;
    inactive: number;
    payout_ready: number;
    missing_salary: number;
    name_mismatch: number;
    monthly_payroll_kobo: number;
  };
  estimate: Breakdown;
  wallet_balance_kobo: number;
  shortfall_kobo: number;
  subscription: Subscription | null;
  last_run: RunSummary | null;
  checklist: { key: string; label: string; done: boolean; link: string }[];
  activity: AuditEntry[];
};

export type Breakdown = { salaries_kobo: number; transfer_fees_kobo: number; commission_kobo: number; total_kobo: number };

export type StaffStatus = "pending" | "registered" | "inactive";

export type Staff = {
  id: string;
  staff_code: string;
  source: "generated" | "uploaded" | "manual";
  status: StaffStatus;
  name: string;
  first_name: string | null;
  last_name: string | null;
  preset_name: string | null;
  email: string | null;
  phone: string | null;
  role_id: string | null;
  role_name: string | null;
  salary_override_kobo: number | null;
  salary_kobo: number;
  bank_code: string | null;
  bank_name: string | null;
  account_number: string | null;
  account_name: string | null;
  name_match: boolean | null;
  bank_verified: boolean;
  payout_ready: boolean;
  registered_at: string | null;
  created_at: string;
  payments?: StaffPayment[];
};

export type StaffPayment = {
  id: string;
  run_id: string;
  run_number: string;
  period: string;
  amount_kobo: number;
  status: ItemStatus;
  paid_at: string | null;
  reference: string;
  failure_reason: string | null;
  bank_name: string | null;
  account_number_masked: string;
};

export type Role = { id: string; name: string; salary_kobo: number; description: string | null; staff_count: number; created_at: string };

export type IdsSummary = { headcount: number; in_use: number; remaining: number };

export type UploadReport = {
  added_count: number;
  added: string[];
  duplicates_in_file: string[];
  already_exists: string[];
  invalid: { line: number; value: string; reason: string }[];
  skipped_count: number;
};

export type RunStatus = "draft" | "awaiting_funding" | "ready" | "processing" | "completed" | "partially_failed" | "failed" | "canceled";
export type ItemStatus = "pending" | "queued" | "processing" | "success" | "failed" | "reversed";

export type PayrollItem = {
  id: string;
  staff_id: string | null;
  staff_code: string;
  staff_name: string;
  role_name: string | null;
  bank_name: string | null;
  account_number_masked: string;
  account_name: string | null;
  amount_kobo: number;
  fee_kobo: number;
  commission_kobo: number;
  status: ItemStatus;
  reference: string;
  failure_reason: string | null;
  refunded: boolean;
  paid_at: string | null;
};

export type FundingQuote = { net_kobo: number; gross_kobo: number; fee_kobo: number };

export type Payment = {
  id: string;
  reference: string;
  purpose: "wallet" | "payroll" | "invoice";
  channel: "checkout" | "transfer" | "dva";
  status: "pending" | "success" | "failed" | "abandoned";
  amount_kobo: number;
  expected_net_kobo: number;
  fee_estimate_kobo: number;
  fees_kobo: number | null;
  net_kobo: number | null;
  authorization_url: string | null;
  payroll_run_id: string | null;
  invoice_id: string | null;
  workgroup_id: string;
  paid_at: string | null;
  created_at: string;
  payroll_run?: PayrollRun | null;
};

export type PayrollRun = RunSummary & {
  workgroup_id: string;
  period_key: string;
  note: string | null;
  transfer_fees_kobo: number;
  commission_kobo: number;
  commission_bps: number;
  commission_label: string;
  refunded_kobo: number;
  submitted_at: string | null;
  funded_at: string | null;
  disbursed_at: string | null;
  canceled_at: string | null;
  failure_reason: string | null;
  items?: PayrollItem[];
  progress?: { success: number; failed: number; processing: number; pending: number; total: number };
  funding?: {
    shortfall_kobo: number;
    request_kobo: number;
    wallet_balance_kobo: number;
    total_kobo: number;
    checkout: FundingQuote | null;
    transfer: (FundingQuote & Dva) | null;
  };
  pending_payment?: Payment | null;
  wallet_balance_kobo?: number;
};

export type Preview = Breakdown & {
  items: {
    staff_id: string;
    staff_code: string;
    staff_name: string;
    role_name: string | null;
    bank_name: string | null;
    account_number_masked: string;
    amount_kobo: number;
    fee_kobo: number;
    commission_kobo: number;
    name_match: boolean | null;
  }[];
  not_ready: { staff_id: string; staff_code: string; staff_name: string; reasons: string[] }[];
  unregistered_count: number;
  commission_bps: number;
  commission_label: string;
  wallet_balance_kobo: number;
  shortfall_kobo: number;
};

export type WalletInfo = {
  balance_kobo: number;
  dva: Dva | null;
  dva_available: boolean;
  estimated_payroll_kobo: number;
  shortfall_kobo: number;
  totals: Record<string, number>;
  payment_mode: "manual" | "automatic";
  next_payday_at: string | null;
};

export type WalletEntry = {
  id: string;
  type: string;
  direction: "credit" | "debit";
  amount_kobo: number;
  balance_after_kobo: number;
  reference: string | null;
  description: string;
  payroll_run_id: string | null;
  created_at: string;
};

export type Invoice = {
  id: string;
  number: string;
  kind: "subscription" | "renewal" | "seats";
  plan_code: string;
  seats: number;
  previous_seats: number | null;
  billing_cycle: "monthly" | "annual";
  period_start: string;
  period_end: string;
  amount_kobo: number;
  status: "pending" | "paid" | "void";
  paid_via: string | null;
  paid_at: string | null;
  description: string | null;
  created_at: string;
};

export type Quote = {
  plan: Plan;
  seats: number;
  billing_cycle: "monthly" | "annual";
  monthly_kobo: number;
  amount_kobo: number;
  months_covered: number;
  months_charged: number;
  per_staff_effective_kobo: number;
  commission_bps: number;
  commission_label: string;
};

export type BillingInfo = {
  subscription: Subscription | null;
  seats_in_use: number;
  quote_monthly: Quote;
  quote_annual: Quote;
  invoices: Invoice[];
  wallet_balance_kobo: number;
  plans: Plan[];
};

export type Notification = {
  id: string;
  title: string;
  body: string;
  kind: "info" | "success" | "warning" | "danger";
  link: string | null;
  workgroup_id: string | null;
  read: boolean;
  created_at: string;
};

export type Meta = {
  app_name: string;
  company_name: string;
  support_email: string;
  commission_bps: number;
  commission_label: string;
  trial_days: number;
  annual_discount_months: number;
  ai_mode: "ai" | "basic";
  payments_sandbox: boolean;
};

export type Bank = { name: string; code: string };

export type AIAction = {
  id: string;
  tool: string;
  summary: string;
  requires_password: boolean;
  status: "pending" | "executed" | "canceled" | "failed" | "expired";
  kind: string;
  result: Record<string, unknown> | null;
  created_at: string;
};

export type AIMessage = { id: string; role: "user" | "assistant"; text: string; created_at: string };

export type AIQuota = { used: number; limit: number; remaining: number };

export type Analytics = {
  series: { month: string; salaries_kobo: number; fees_kobo: number; staff_paid: number }[];
  headcount: { month: string; registered: number }[];
  by_role: { role: string; staff: number; salaries_kobo: number }[];
  totals: {
    lifetime_paid_kobo: number;
    lifetime_fees_kobo: number;
    payments_count: number;
    failed_count: number;
    success_rate: number | null;
    funded_kobo: number;
    monthly_payroll_kobo: number;
    median_salary_kobo: number;
    average_salary_kobo: number;
    month_change_pct: number | null;
  };
};

export type Withdrawal = {
  id: string;
  number: string;
  amount_kobo: number;
  fee_kobo: number;
  total_kobo: number;
  bank_code: string;
  bank_name: string;
  account_number: string;
  account_number_masked: string;
  account_name: string;
  status: "queued" | "processing" | "success" | "failed" | "reversed";
  failure_reason: string | null;
  refunded: boolean;
  reference: string;
  created_at: string;
  completed_at: string | null;
};

export type WithdrawalQuote = {
  amount_kobo: number;
  fee_kobo: number;
  total_kobo: number;
  balance_kobo: number;
  max_amount_kobo: number;
  min_amount_kobo: number;
  enough: boolean;
};
