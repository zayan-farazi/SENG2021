export const LIVE_REFRESH_INTERVAL_MS = 10_000;

const lastUpdatedFormatter = new Intl.DateTimeFormat("en-AU", {
  hour: "numeric",
  minute: "2-digit",
});

export function buildLiveRefreshLabel(
  lastUpdatedAt: number | null,
  refreshing: boolean,
): string {
  if (refreshing && lastUpdatedAt === null) {
    return "Refreshing listings...";
  }

  if (refreshing) {
    return "Refreshing listings...";
  }

  if (lastUpdatedAt === null) {
    return "Waiting for first sync";
  }

  return `Last updated ${lastUpdatedFormatter.format(lastUpdatedAt)}`;
}
