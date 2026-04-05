import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterPage } from "./pages/RegisterPage";
import { SESSION_STORAGE_KEY, setStoredSession } from "./session";

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
        partyId: "team@acmebooks.com",
        partyName: "Acme Books",
        contactEmail: "team@acmebooks.com",
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
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/v2/parties/register",
      expect.objectContaining({
        method: "POST",
      }),
    );
    await waitFor(() => {
      expect(screen.getByText(/registration complete/i)).toBeInTheDocument();
    });
    expect(screen.getAllByText("team@acmebooks.com")).toHaveLength(2);
    expect(JSON.parse(window.localStorage.getItem(SESSION_STORAGE_KEY) ?? "{}")).toEqual({
      partyId: "team@acmebooks.com",
      partyName: "Acme Books",
      contactEmail: "team@acmebooks.com",
      credential: "super-secure-password",
    });
    expect(window.location.pathname).toBe("/register");
    expect(screen.getByText(/registration complete/i)).toBeInTheDocument();
  });

  it("continues to the requested protected route after registration success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      status: 201,
      json: async () => ({
        partyId: "team@acmebooks.com",
        partyName: "Acme Books",
        contactEmail: "team@acmebooks.com",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    window.history.replaceState({}, "", "/register?next=%2Forders%2Fcreate");

    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText(/party name/i), {
      target: { value: "Acme Books" },
    });
    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "team@acmebooks.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    await waitFor(() => {
      expect(screen.getByText(/registration complete/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders/create");
    });
  });

  it("shows the already-signed-in state when a session already exists", () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });

    render(<RegisterPage />);

    expect(screen.getByText(/already signed in/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /register party/i })).not.toBeInTheDocument();
  });

  it("uses the requested next route from the already-signed-in state", async () => {
    setStoredSession({
      partyId: "buyer@example.com",
      partyName: "Buyer Co",
      contactEmail: "buyer@example.com",
      credential: "super-secure-password",
    });
    window.history.replaceState({}, "", "/register?next=%2Forders%2Fcreate");

    render(<RegisterPage />);

    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => {
      expect(window.location.pathname).toBe("/orders/create");
    });
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
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "super-secure-password" },
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

    fireEvent.change(screen.getByLabelText(/party name/i), { target: { value: "Acme Books" } });
    fireEvent.change(screen.getByLabelText(/contact email/i), { target: { value: "not-an-email" } });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    await waitFor(() => {
      expect(screen.getByText("Field required")).toBeInTheDocument();
      expect(screen.getByText(/value is not a valid email address/i)).toBeInTheDocument();
    });
  });

  it("shows a local validation error when the passwords do not match", async () => {
    render(<RegisterPage />);

    fireEvent.change(screen.getByLabelText(/party name/i), { target: { value: "Acme Books" } });
    fireEvent.change(screen.getByLabelText(/contact email/i), {
      target: { value: "team@acmebooks.com" },
    });
    fireEvent.change(screen.getByLabelText(/^password$/i), {
      target: { value: "super-secure-password" },
    });
    fireEvent.change(screen.getByLabelText(/confirm password/i), {
      target: { value: "different-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: /register party/i }));

    await waitFor(() => {
      expect(screen.getByText(/passwords must match/i)).toBeInTheDocument();
    });
  });
});
