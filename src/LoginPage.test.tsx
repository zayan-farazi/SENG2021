import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./pages/LoginPage";
import { SESSION_STORAGE_KEY, setStoredSession } from "./session";

describe("LoginPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/login");
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("logs in with contact email and password and stores the session locally", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({
        partyId: "buyer@example.com",
        partyName: "Buyer Co",
        contactEmail: "buyer@example.com",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "buyer@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^log in$/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v2/parties/login",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          contactEmail: "buyer@example.com",
          password: "super-secure-password",
        }),
      }),
    );

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders");
    });

    expect(JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) ?? "{}")).toEqual({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
  });

  it("continues to the requested protected route after login", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 200,
      json: async () => ({
        partyId: "buyer@example.com",
        partyName: "Buyer Co",
        contactEmail: "buyer@example.com",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/login?next=%2Forders%2Fcreate");

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "buyer@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^log in$/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders/create");
    });
  });

  it("shows an auth error when the email and password are invalid", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 401,
        json: async () => ({ detail: "Unauthorized" }),
      }),
    );

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "buyer@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "wrong-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^log in$/i }));

    await waitFor(() => {
      expect(screen.getByText(/not recognized/i)).toBeInTheDocument();
    });
    expect(window.localStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });

  it("shows the already-signed-in state when a session already exists", () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<LoginPage />);

    expect(screen.getByText(/already signed in/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^log in$/i })).not.toBeInTheDocument();
  });

  it("uses the requested next route from the already-signed-in state", async () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    window.history.replaceState({}, "", "/login?next=%2Forders%2Fcreate");

    render(<LoginPage />);

    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders/create");
    });
  });
});
