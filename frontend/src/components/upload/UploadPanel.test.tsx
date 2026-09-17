import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import UploadPanel from "./UploadPanel";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function csvFile(name = "ads.csv"): File {
  return new File(["date,campaign_id,placement\n2026-09-01,c1,feed\n"], name, { type: "text/csv" });
}

/**
 * userEvent's internal event choreography relies on real setTimeout/MessageChannel
 * flushing that deadlocks under vi.useFakeTimers() in this React 19 + jsdom combo
 * (confirmed with a minimal userEvent.click() repro outside this component too).
 * fireEvent dispatches synchronously and is what the fake-timer polling tests use.
 */
function selectFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  fireEvent.change(input);
}

const validatedUpload = {
  id: 12,
  uploaded_at: "2026-09-16T09:00:00Z",
  original_filename: "ads.csv",
  row_count: 900,
  date_range_start: "2026-08-01",
  date_range_end: "2026-08-31",
  status: "validated",
  validation_report: { errors: [], warnings: [] },
};

const queuedRun = {
  id: 5,
  upload_id: 12,
  status: "queued",
  review_status: "pending",
  headline_waste: null,
  error_message: null,
  created_at: "2026-09-16T09:00:05Z",
};

afterEach(() => {
  vi.useRealTimers();
});

describe("UploadPanel", () => {
  it("uploads a chosen file as multipart with the field name 'file'", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validatedUpload, 201));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/uploads", expect.anything()));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const body = init.body as FormData;
    expect(init.method).toBe("POST");
    expect((body.get("file") as File).name).toBe("ads.csv");
    expect(await screen.findByText(/900 rows/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled();
  });

  it("refuses a non-CSV file before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<UploadPanel />);

    // The input carries accept=".csv", but that is only advisory — a user can switch the
    // native picker to "All files". fireEvent bypasses user-event's accept filter so this
    // test exercises the JS guard, which is the thing that actually has to hold.
    const input = screen.getByLabelText("Choose a CSV file") as HTMLInputElement;
    Object.defineProperty(input, "files", {
      configurable: true,
      value: [new File(["%PDF"], "report.pdf", { type: "application/pdf" })],
    });
    fireEvent.change(input);

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload a .csv file");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("tables the row-level errors from a 422 body and offers no Analyze button", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: {
              errors: [
                { row: 4, column: "spend", message: "not a number: 'abc'" },
                { row: 9, column: "clicks", message: "clicks (50) exceed impressions (10)" },
              ],
              warnings: [{ row: 11, column: "conversions", message: "conversions exceed clicks" }],
            },
          },
          422,
        ),
      ),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByText("not a number: 'abc'")).toBeInTheDocument();
    expect(screen.getByText("clicks (50) exceed impressions (10)")).toBeInTheDocument();
    expect(screen.getByText("conversions exceed clicks")).toBeInTheDocument();
    expect(screen.getByText("Row 4")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze" })).not.toBeInTheDocument();
  });

  it("tables the errors when the API accepts the file but marks it failed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            ...validatedUpload,
            status: "failed",
            validation_report: {
              errors: [{ row: null, column: "revenue", message: "missing column" }],
              warnings: [],
            },
          },
          201,
        ),
      ),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByText("missing column")).toBeInTheDocument();
    expect(screen.getByText("Whole file")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Analyze" })).not.toBeInTheDocument();
  });

  it("explains a duplicate upload and offers to analyse the existing one", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ detail: { message: "this file was already uploaded", upload_id: 12 } }, 409),
        )
        .mockResolvedValueOnce(jsonResponse(queuedRun, 202)),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByRole("alert")).toHaveTextContent("this file was already uploaded");
    const analyzeExisting = screen.getByRole("button", { name: /analyse the existing upload/i });
    await user.click(analyzeExisting);
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/analyze/12", expect.anything()));
  });

  it("shows the file size message on a 413", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: { message: "file is larger than 20 MB", max_upload_mb: 20 } }, 413)),
    );
    const user = userEvent.setup();
    render(<UploadPanel />);

    await user.upload(screen.getByLabelText("Choose a CSV file"), csvFile());

    expect(await screen.findByRole("alert")).toHaveTextContent("file is larger than 20 MB");
  });

  it("starts a run, polls every 2 seconds, and stops at 'awaiting admin review'", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
      .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
      .mockResolvedValueOnce(jsonResponse({ ...queuedRun, status: "running" }))
      .mockResolvedValue(
        jsonResponse({ ...queuedRun, status: "done", review_status: "pending", headline_waste: 100000 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<UploadPanel />);

    selectFile(screen.getByLabelText("Choose a CSV file") as HTMLInputElement, csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));

    await vi.waitFor(() => expect(screen.getByText(/Queued/)).toBeInTheDocument());

    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(screen.getByText(/Running/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith("/api/runs/5", expect.anything());

    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => expect(screen.getByText(/awaiting admin review/i)).toBeInTheDocument());

    const callsAfterDone = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(6000);
    expect(fetchMock.mock.calls.length).toBe(callsAfterDone);
  });

  it("links to the report when the run comes back already approved", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
        .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
        .mockResolvedValue(
          jsonResponse({ ...queuedRun, status: "done", review_status: "approved", headline_waste: 100000 }),
        ),
    );
    render(<UploadPanel />);

    selectFile(screen.getByLabelText("Choose a CSV file") as HTMLInputElement, csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await vi.waitFor(() => expect(screen.getByText(/Queued/)).toBeInTheDocument());
    await vi.advanceTimersByTimeAsync(2000);

    const link = await vi.waitFor(() => screen.getByRole("link", { name: "See the report" }));
    expect(link).toHaveAttribute("href", "/dashboard/reports/5");
  });

  it("shows the backend error message when the run fails", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
        .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
        .mockResolvedValue(
          jsonResponse({ ...queuedRun, status: "failed", error_message: "no significant segments" }),
        ),
    );
    render(<UploadPanel />);

    selectFile(screen.getByLabelText("Choose a CSV file") as HTMLInputElement, csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await vi.waitFor(() => expect(screen.getByText(/Queued/)).toBeInTheDocument());
    await vi.advanceTimersByTimeAsync(2000);

    await vi.waitFor(() => expect(screen.getByText("no significant segments")).toBeInTheDocument());
  });

  it("accepts a file dropped on the drop zone", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(validatedUpload, 201));
    vi.stubGlobal("fetch", fetchMock);
    render(<UploadPanel />);

    fireEvent.drop(screen.getByTestId("drop-zone"), {
      dataTransfer: { files: [csvFile("dropped.csv")], types: ["Files"] },
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = (fetchMock.mock.calls[0][1] as RequestInit).body as FormData;
    expect((body.get("file") as File).name).toBe("dropped.csv");
  });

  it("stops polling and clears the interval on unmount", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(validatedUpload, 201))
      .mockResolvedValueOnce(jsonResponse(queuedRun, 202))
      .mockResolvedValue(jsonResponse({ ...queuedRun, status: "running" }));
    vi.stubGlobal("fetch", fetchMock);
    const { unmount } = render(<UploadPanel />);

    selectFile(screen.getByLabelText("Choose a CSV file") as HTMLInputElement, csvFile());
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Analyze" })).toBeEnabled());
    fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
    await vi.waitFor(() => expect(screen.getByText(/Queued/)).toBeInTheDocument());

    unmount();
    const callsAtUnmount = fetchMock.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetchMock.mock.calls.length).toBe(callsAtUnmount);
  });
});
