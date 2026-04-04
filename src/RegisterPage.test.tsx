import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterPage } from "./pages/RegisterPage";
import { SESSION_STORAGE_KEY } from "./session";

describe("RegisterPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/register");
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("registers a party, stores the session locally, and keeps the success screen visible", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 201,
      json: async () => ({
        partyId: "acme-books",
        partyName: "Acme Books",
        appKey: "appkey_live_123example",
        message: "Store this key securely. It will not be shown again.",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText(/party name/i), {
      target: { value: "Acme Books" },
    });
    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "team@acmebooks.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v1/parties/register",
      expect.objectContaining({
        method: "POST",
      }),
    );
    await waitFor(() => {
      expect(screen.getByText(/registration complete/i)).toBeInTheDocument();
    });
    expect(screen.getByText("acme-books")).toBeInTheDocument();
    expect(screen.getByText("appkey_live_123example")).toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) ?? "{}")).toEqual({
      partyId: "acme-books",
      partyName: "Acme Books",
      contactEmail: "team@acmebooks.com",
      appKey: "appkey_live_123example",
    });
    expect(window.location.pathname).toBe("/register");
    expect(screen.getByText(/already signed in/i)).toBeInTheDocument();
  });

  it("shows duplicate-email failures returned by the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 409,
        json: async () => ({
          detail: "A party with this contact email already exists.",
        }),
      }),
    );

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText(/party name/i), { target: { value: "Acme Books" } });
    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "team@acmebooks.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    await waitFor(() => {
      expect(screen.getByText(/already exists/i)).toBeInTheDocument();
    });
  });

  it("maps backend validation failures onto the registration form", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 422,
        json: async () => ({
          message: "Request validation failed.",
          errors: [
            { path: "partyName", message: "Field required" },
            { path: "contactEmail", message: "value is not a valid email address" },
          ],
        }),
      }),
    );

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText(/party name/i), { target: { value: " " } });
    fireEvent.change(screen.getByLabelText(/contact email/i), { target: { value: "not-an-email" } });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    await waitFor(() => {
      expect(screen.getByText("Field required")).toBeInTheDocument();
      expect(screen.getByText(/value is not a valid email address/i)).toBeInTheDocument();
    });
  });
});
