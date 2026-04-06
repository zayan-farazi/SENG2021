import { afterEach, describe, expect, it, vi } from "vitest";

describe("voiceOrder URLs", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("falls back to the browser location when process is unavailable", async () => {
    vi.stubEnv("BUN_PUBLIC_BACKEND_URL", "");
    const { getBackendHttpUrl, getBackendWebSocketUrl } = await import("./voiceOrder");

    expect(getBackendHttpUrl()).toBe("http://localhost:8000");
    expect(getBackendWebSocketUrl()).toBe("ws://localhost:8000/v1/order/draft/ws");
  });

  it("prefers the configured backend URL and trims a trailing slash", async () => {
    vi.stubEnv("BUN_PUBLIC_BACKEND_URL", "https://orders.example.test/");
    const { getBackendHttpUrl, getBackendWebSocketUrl } = await import("./voiceOrder");

    expect(getBackendHttpUrl()).toBe("https://orders.example.test");
    expect(getBackendWebSocketUrl()).toBe("wss://orders.example.test/v1/order/draft/ws");
  });
});
