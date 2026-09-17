import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AuthForm from "./AuthForm";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const meOut = {
  user: { id: 1, email: "owner@shop.pk", role: "client", created_at: "2026-09-16T00:00:00Z" },
  client: { id: 1, business_name: "Shop", base_fee: "15000.00", performance_fee_pct: "20.00" },
};

beforeEach(() => {
  push.mockClear();
  refresh.mockClear();
});

describe("AuthForm", () => {
  it("shows only email and password in login mode", () => {
    render(<AuthForm mode="login" />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.queryByLabelText("Business name")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
  });

  it("asks for a business name in signup mode", () => {
    render(<AuthForm mode="signup" />);

    expect(screen.getByLabelText("Business name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("posts the login payload and goes to the dashboard", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(meOut));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    expect(fetchMock).toHaveBeenCalledWith("/api/auth/login", expect.objectContaining({ method: "POST" }));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      email: "owner@shop.pk",
      password: "correct-horse",
    });
    expect(refresh).toHaveBeenCalled();
  });

  it("includes the business name in the signup payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(meOut, 201));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Business name"), "Kolachi Kitchen");
    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/dashboard"));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      email: "owner@shop.pk",
      password: "correct-horse",
      business_name: "Kolachi Kitchen",
    });
  });

  it("shows the backend detail on a 401 and stays put", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "invalid credentials" }, 401)));
    const user = userEvent.setup();
    render(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email"), "owner@shop.pk");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("invalid credentials");
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a friendly message when the email is taken", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "email already registered" }, 409)));
    const user = userEvent.setup();
    render(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Business name"), "Shop");
    await user.type(screen.getByLabelText("Email"), "taken@shop.pk");
    await user.type(screen.getByLabelText("Password"), "correct-horse");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("email already registered");
  });
});
