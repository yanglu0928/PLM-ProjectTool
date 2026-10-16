import { afterEach, describe, expect, it, vi } from "vitest";

import { isBackendReady } from "@/shared/api/healthClient";

function response(ok: boolean, payload: unknown): Response {
  return {
    ok,
    json: vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

describe("isBackendReady", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("uses the same-origin minimal health endpoint", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(true, { status: "UP" }));

    await expect(
      isBackendReady(fetcher as unknown as typeof fetch),
    ).resolves.toBe(true);
    expect(fetcher).toHaveBeenCalledWith(
      "/health/ready",
      expect.objectContaining({
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
      }),
    );
  });

  it("fails closed on a non-success response", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(false, { status: "UP" }));

    await expect(
      isBackendReady(fetcher as unknown as typeof fetch),
    ).resolves.toBe(false);
  });

  it("fails closed on an invalid payload", async () => {
    const fetcher = vi.fn().mockResolvedValue(response(true, { version: "secret" }));

    await expect(
      isBackendReady(fetcher as unknown as typeof fetch),
    ).resolves.toBe(false);
  });

  it("does not expose transport errors", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("private host and path"));

    await expect(
      isBackendReady(fetcher as unknown as typeof fetch),
    ).resolves.toBe(false);
  });
});
