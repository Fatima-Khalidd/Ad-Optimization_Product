// Mirrors backend/app/schemas/admin.py. Every Decimal is a JSON string ("19600.00").

export type AdminClient = {
  id: number;
  business_name: string;
  contact_info: string | null;
  pricing_model: string;
  base_fee: string;
  performance_fee_pct: string;
  config_overrides: Record<string, unknown>;
  created_at: string;
};

export type RunDimension = {
  dimension: string;
  total_spend: string;
  total_wasted_spend: string;
  benchmark_cpa: string | null;
};

export type FlaggedSegment = {
  dimension: string;
  segment_value: string;
  spend: string;
  conversions: number;
  cpa: string | null;
  wasted_spend: string;
};

export type AdminRun = {
  id: number;
  client_id: number;
  business_name: string;
  upload_id: number;
  status: string;
  review_status: "pending" | "approved" | "rejected";
  headline_waste: string | null;
  review_note: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  created_at: string;
  dimensions: RunDimension[];
  flagged_segments: FlaggedSegment[];
  config_snapshot: Record<string, unknown>;
};

export type AdminInvoice = {
  id: number;
  invoice_number: string;
  client_id: number;
  business_name: string;
  period_start: string;
  period_end: string;
  due_date: string;
  base_fee: string;
  suggested_recovered_waste: string;
  confirmed_recovered_waste: string;
  performance_fee: string;
  total: string;
  amount_paid: string;
  status: "draft" | "issued" | "payment_submitted" | "paid" | "void";
  confirmed_by: number | null;
  issued_at: string | null;
  created_at: string;
};

export type AuditEntry = {
  id: number;
  actor_user_id: number | null;
  action: string;
  entity_type: string;
  entity_id: number;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
};

/** PATCH body for /api/admin/clients/{id} — matches backend ClientPatch. */
export type ClientPatch = {
  base_fee?: string;
  performance_fee_pct?: string;
  config_overrides?: Record<string, unknown>;
};
