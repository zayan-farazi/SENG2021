import { afterEach, describe, expect, it, vi } from "vitest";
import { getBackendHttpUrl, getBackendWebSocketUrl } from "./voiceOrder";

describe("voiceOrder URLs", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("falls back to the browser location when process is unavailable", () => {
    vi.stubGlobal("process", undefined);

    expect(getBackendHttpUrl()).toBe("http://localhost:8000");
    expect(getBackendWebSocketUrl()).toBe("ws://localhost:8000/v1/order/draft/ws");
  });

  it("prefers the configured backend URL and trims a trailing slash", () => {
    vi.stubGlobal("process", {
      env: { BUN_PUBLIC_BACKEND_URL: "https://orders.example.test/" },
    });

    expect(getBackendHttpUrl()).toBe("https://orders.example.test");
    expect(getBackendWebSocketUrl()).toBe("wss://orders.example.test/v1/order/draft/ws");
  });
});
