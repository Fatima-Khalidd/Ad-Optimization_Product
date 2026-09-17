"use client";

import Link from "next/link";
import { useEffect, useState, type DragEvent } from "react";

import Button from "@/components/ui/Button";
import IssueTable from "@/components/upload/IssueTable";
import { ApiError, apiFetch, extractIssues } from "@/lib/api";
import type { RunOut, UploadOut, ValidationReport } from "@/lib/types";

const POLL_MS = 2000;
const MAX_POLL_ATTEMPTS = 150; // ~5 minutes at 2s/poll

const RUN_LABELS: Record<RunOut["status"], string> = {
  queued: "Queued — waiting to start.",
  running: "Running — crunching your segments.",
  done: "Done.",
  failed: "Failed.",
};

/** Shape of the 409/413 `detail` bodies (Stage 4 backend contract). Both carry a
 *  human-readable `message`; 409 also carries the existing upload's id. */
type FriendlyDetail = { message?: unknown; upload_id?: unknown };

function friendlyMessage(detail: unknown, fallback: string): string {
  if (detail !== null && typeof detail === "object") {
    const candidate = (detail as FriendlyDetail).message;
    if (typeof candidate === "string" && candidate.length > 0) return candidate;
  }
  return fallback;
}

function duplicateUploadIdFrom(detail: unknown): number | null {
  if (detail !== null && typeof detail === "object") {
    const candidate = (detail as FriendlyDetail).upload_id;
    if (typeof candidate === "number") return candidate;
  }
  return null;
}

export default function UploadPanel() {
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateUploadId, setDuplicateUploadId] = useState<number | null>(null);
  const [upload, setUpload] = useState<UploadOut | null>(null);
  const [issues, setIssues] = useState<ValidationReport>({ errors: [], warnings: [] });
  const [run, setRun] = useState<RunOut | null>(null);
  const [pollTimedOut, setPollTimedOut] = useState(false);

  const runId = run?.id;
  const runStatus = run?.status;

  // Poll the run until it settles. Re-armed whenever the status changes, torn
  // down on unmount, and never armed again once the run is done or failed.
  // Capped at MAX_POLL_ATTEMPTS so a stuck backend can't spin this forever.
  useEffect(() => {
    if (runId === undefined || runStatus === "done" || runStatus === "failed") return;

    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      if (attempts > MAX_POLL_ATTEMPTS) {
        clearInterval(timer);
        setPollTimedOut(true);
        return;
      }
      apiFetch<RunOut>(`/api/runs/${runId}`)
        .then(setRun)
        .catch(() => {
          clearInterval(timer);
          setError("Lost contact with the server while the analysis was running. Reload to check again.");
        });
    }, POLL_MS);

    return () => clearInterval(timer);
  }, [runId, runStatus]);

  async function send(file: File) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Upload a .csv file — that is what the ad platforms export.");
      return;
    }

    setBusy(true);
    setError(null);
    setDuplicateUploadId(null);
    setUpload(null);
    setRun(null);
    setPollTimedOut(false);
    setIssues({ errors: [], warnings: [] });

    const form = new FormData();
    form.append("file", file);

    try {
      const result = await apiFetch<UploadOut>("/api/uploads", { method: "POST", body: form });
      setUpload(result);
      setIssues(extractIssues(result.validation_report));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 422) {
        setIssues(extractIssues(caught.detail));
      } else if (caught instanceof ApiError && caught.status === 409) {
        setError(friendlyMessage(caught.detail, caught.message));
        setDuplicateUploadId(duplicateUploadIdFrom(caught.detail));
      } else if (caught instanceof ApiError && caught.status === 413) {
        setError(friendlyMessage(caught.detail, caught.message));
      } else if (caught instanceof ApiError) {
        setError(caught.message);
      } else {
        setError("Could not reach the server. Check your connection and try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function analyzeUploadId(id: number) {
    setError(null);
    try {
      setRun(await apiFetch<RunOut>(`/api/analyze/${id}`, { method: "POST" }));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not start the analysis.");
    }
  }

  async function analyze() {
    if (upload === null) return;
    await analyzeUploadId(upload.id);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) void send(file);
  }

  const canAnalyze = upload !== null && upload.status !== "failed" && issues.errors.length === 0;

  return (
    <div className="max-w-3xl">
      <h1 className="font-display text-4xl leading-tight">Upload an export.</h1>
      <p className="mt-3 max-w-xl text-slate">
        One CSV of your daily rows. Breakdowns your platform cannot export together may be left blank — each
        dimension is analysed only on the rows that carry it.{" "}
        <a className="text-teal underline underline-offset-4" href="/api/uploads/template.csv">
          Download the template
        </a>
        .
      </p>

      <div
        className={`mt-10 flex flex-col items-center gap-4 rounded-sm border border-dashed px-6 py-16 text-center transition-colors ${
          dragging ? "border-teal bg-surface" : "border-slate/40"
        }`}
        data-testid="drop-zone"
        onDragLeave={() => setDragging(false)}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDrop={onDrop}
      >
        <p className="text-slate">Drag your CSV here</p>
        <label className="cursor-pointer text-sm text-teal underline underline-offset-4" htmlFor="csv-input">
          Choose a CSV file
        </label>
        <input
          className="sr-only"
          id="csv-input"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void send(file);
            event.target.value = "";
          }}
          type="file"
        />
      </div>

      {busy ? <p className="mt-6 text-slate">Uploading and validating…</p> : null}

      {error ? (
        <div className="mt-6">
          <p className="text-coral" role="alert">
            {error}
          </p>
          {duplicateUploadId !== null ? (
            <Button
              className="mt-3"
              onClick={() => analyzeUploadId(duplicateUploadId)}
              type="button"
              variant="ghost"
            >
              Analyse the existing upload
            </Button>
          ) : null}
        </div>
      ) : null}

      {upload !== null && upload.status !== "failed" ? (
        <p className="mt-8 text-paper">
          <span className="font-display text-2xl">{upload.original_filename}</span>{" "}
          <span className="text-slate">
            — {upload.row_count ?? 0} rows
            {upload.date_range_start && upload.date_range_end
              ? `, ${upload.date_range_start} to ${upload.date_range_end}`
              : ""}
          </span>
        </p>
      ) : null}

      <IssueTable issues={issues.errors} title="Rows we could not read" tone="error" />
      <IssueTable issues={issues.warnings} title="Worth a look" tone="warning" />

      {canAnalyze && run === null ? (
        <div className="mt-10">
          <Button onClick={analyze} type="button">
            Analyze
          </Button>
        </div>
      ) : null}

      {run !== null ? (
        <div className="mt-10 border-t border-slate/20 pt-6">
          <p className="text-paper">{RUN_LABELS[run.status]}</p>
          {run.status === "failed" && run.error_message ? (
            <p className="mt-2 text-coral">{run.error_message}</p>
          ) : null}
          {run.status === "done" && run.review_status !== "approved" ? (
            <p className="mt-2 max-w-xl text-slate">
              Your numbers are in and awaiting admin review. We check every run before it reaches you — the
              report appears on your dashboard as soon as it is approved.
            </p>
          ) : null}
          {run.status === "done" && run.review_status === "approved" ? (
            <Link
              className="mt-3 inline-block text-teal underline underline-offset-4"
              href={`/dashboard/reports/${run.id}`}
            >
              See the report
            </Link>
          ) : null}
          {run.status !== "done" && run.status !== "failed" && pollTimedOut ? (
            <p className="mt-2 max-w-xl text-slate">
              This is taking longer than usual. It is still running on the server — check back in a few
              minutes.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
