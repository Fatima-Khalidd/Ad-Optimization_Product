/**
 * TypeScript mirrors of the backend Pydantic schemas.
 * Source of truth: docs/superpowers/plans/INTERFACES.md, Stage 2 and Stage 3,
 * cross-checked against backend/app/schemas/*.py.
 *
 * Decimal (money/percentage) fields are typed `string` — Pydantic v2 serialises
 * `Decimal` as a JSON string matching `-?\d+\.\d{2}` (INTERFACES.md "Stage 3
 * close-out", binding for Stages 4-8). Formatting helpers in format.ts parse
 * them; components must never assume a field carrying money is a `number`.
 */

export type Dimension = "placement" | "age_group" | "time_slot";

export const DIMENSIONS: readonly Dimension[] = ["placement", "age_group", "time_slot"];

export const DIMENSION_LABELS: Record<Dimension, string> = {
  placement: "Placement",
  age_group: "Age group",
  time_slot: "Time slot",
};

export interface SegmentOut {
  segment: string;
  /** Money — decimal string, e.g. "84000.00". */
  spend: string;
  impressions: number;
  clicks: number;
  conversions: number;
  /** Money — decimal string. */
  revenue: string;
  /** Money — decimal string, or null (backend: `Decimal | None`). */
  cpa: string | null;
  /** Ratio, not money — always a number, 0.0 (never null) when the denominator is 0. */
  ctr: number;
  /** Ratio, not money — always a number, 0.0 (never null) when the denominator is 0. */
  cvr: number;
  /** Ratio, not money — null only when spend is 0. */
  roas: number | null;
  is_significant: boolean;
  is_flagged: boolean;
  /** Money — decimal string. */
  wasted_spend: string;
  flag_reason: "zero_conversions" | "high_cpa" | null;
}

export interface DimensionOut {
  dimension: Dimension;
  /** Money — decimal string, or null. */
  benchmark_cpa: string | null;
  /** Money — decimal string. */
  total_spend: string;
  /** Money — decimal string. */
  total_wasted_spend: string;
  segments: SegmentOut[];
}

export interface RecommendationOut {
  id: number;
  dimension: Dimension;
  segment_name: string;
  /** Money — decimal string. */
  current_spend: string;
  /** Money — decimal string. */
  recommended_cut: string;
  reason: string;
}

export interface ReportOut {
  run_id: number;
  upload_id: number;
  /** ISO datetime. May be naive (SQLite/dev) or offset-aware (Postgres/prod) — never assume a trailing "Z". */
  generated_at: string;
  date_range_start: string | null;
  date_range_end: string | null;
  /** Money — the ACCOUNT total (Stage 3 close-out #1), decimal string. */
  total_spend: string;
  /** Money — decimal string. */
  headline_waste: string;
  /** Percentage — decimal string, e.g. "16.28" (Stage 3 close-out #1). */
  recovery_pct: string;
  dimensions: DimensionOut[];
  recommendations: RecommendationOut[];
  config_snapshot: Record<string, unknown>;
}

/** One loader complaint. `row` is 1-based and null for whole-file problems. */
export interface RowIssue {
  row: number | null;
  column: string | null;
  message: string;
}

export interface ValidationReport {
  errors: RowIssue[];
  warnings: RowIssue[];
}

export type UploadStatus = "uploaded" | "validated" | "failed";

export interface UploadOut {
  id: number;
  uploaded_at: string;
  original_filename: string;
  row_count: number | null;
  date_range_start: string | null;
  date_range_end: string | null;
  status: UploadStatus;
  /** The backend column is a bare JSONB dict (never null), so it is NOT guaranteed to
   *  carry `errors`/`warnings`. Narrow it with `extractIssues()` instead of indexing it. */
  validation_report: Record<string, unknown>;
}

export type RunStatus = "queued" | "running" | "done" | "failed";
export type ReviewStatus = "pending" | "approved" | "rejected";

export interface RunOut {
  id: number;
  upload_id: number;
  status: RunStatus;
  review_status: ReviewStatus;
  /** Money — decimal string, or null while the run has not finished. */
  headline_waste: string | null;
  error_message: string | null;
  created_at: string;
}

export interface UserOut {
  id: number;
  email: string;
  role: "client" | "admin";
  created_at: string;
}

export interface ClientOut {
  id: number;
  business_name: string;
  /** Money — decimal string. */
  base_fee: string;
  /** Percentage — decimal string. */
  performance_fee_pct: string;
}

export interface MeOut {
  user: UserOut;
  client: ClientOut | null;
}

/**
 * Stage 7 payloads. Declared here because INTERFACES puts them in types.ts.
 * Mirrors backend/app/schemas/billing.py field-for-field. Money fields are
 * decimal strings (see the module docblock above) — never numbers.
 */
export type InvoiceStatus = "draft" | "issued" | "payment_submitted" | "paid" | "void";
export type MethodType = "jazzcash" | "easypaisa" | "nayapay" | "raast" | "bank_iban";

export interface PaymentInstruction {
  method_type: MethodType;
  account_title: string;
  account_identifier: string;
  instructions: string | null;
}

export interface PaymentMethod {
  id: number;
  type: MethodType;
  account_title: string;
  account_identifier: string;
  instructions: string | null;
  is_active: boolean;
  sort_order: number;
}

export interface Payment {
  id: number;
  method_type: MethodType;
  transaction_ref: string;
  /** Money — decimal string. */
  amount: string;
  paid_at: string;
  status: "pending" | "confirmed" | "rejected";
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
  has_proof: boolean;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  period_start: string;
  period_end: string;
  due_date: string;
  /** Money — decimal string. */
  base_fee: string;
  /** Money — decimal string. */
  confirmed_recovered_waste: string;
  /** Money — decimal string. */
  performance_fee: string;
  /** Money — decimal string. */
  total: string;
  /** Money — decimal string. */
  amount_paid: string;
  /** Money — decimal string. */
  amount_due: string;
  status: InvoiceStatus;
  issued_at: string | null;
  created_at: string;
  is_overdue: boolean;
  payments: Payment[];
  instructions: PaymentInstruction[];
}

export interface AdminPayment extends Payment {
  client_id: number;
  business_name: string;
  invoice_id: number;
  invoice_number: string;
  /** Money — decimal string. */
  invoice_total: string;
  invoice_due_date: string;
  invoice_status: InvoiceStatus;
  invoice_is_overdue: boolean;
}
