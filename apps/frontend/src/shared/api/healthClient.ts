interface HealthPayload {
  status: "UP" | "NOT_READY";
}

export async function isBackendReady(
  fetcher: typeof fetch = fetch,
  timeoutMs = 3_000,
): Promise<boolean> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetcher("/health/ready", {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        Accept: "application/json",
      },
      signal: controller.signal,
    });
    if (!response.ok) {
      return false;
    }
    const payload: unknown = await response.json();
    return isHealthPayload(payload) && payload.status === "UP";
  } catch {
    return false;
  } finally {
    window.clearTimeout(timeout);
  }
}

function isHealthPayload(value: unknown): value is HealthPayload {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const status = (value as Record<string, unknown>).status;
  return status === "UP" || status === "NOT_READY";
}
