export type StoredSession = {
  partyId: string;
  partyName: string;
  contactEmail: string;
  appKey: string;
};

export const SESSION_STORAGE_KEY = "lockedout.session";

function isStoredSession(value: unknown): value is StoredSession {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.partyId === "string" &&
    typeof candidate.partyName === "string" &&
    typeof candidate.contactEmail === "string" &&
    typeof candidate.appKey === "string"
  );
}

export function getStoredSession(): StoredSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    return isStoredSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function setStoredSession(session: StoredSession) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
}

export function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

export function hasStoredSession(): boolean {
  return Boolean(getStoredSession());
}
