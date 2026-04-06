import { useEffect, useState } from "react";

export type StoredSession = {
  partyId: string;
  partyName: string;
  contactEmail: string;
  credential: string;
};

export const SESSION_STORAGE_KEY = "lockedout.session";
const SESSION_CHANGE_EVENT = "lockedout:session-change";

function isStoredSession(value: unknown): value is StoredSession {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.partyId === "string" &&
    typeof candidate.partyName === "string" &&
    typeof candidate.contactEmail === "string" &&
    (typeof candidate.credential === "string" || typeof candidate.appKey === "string")
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
    if (!isStoredSession(parsed)) {
      return null;
    }

    const candidate = parsed as Record<string, string>;
    return {
      partyId: candidate.partyId,
      partyName: candidate.partyName,
      contactEmail: candidate.contactEmail,
      credential: candidate.credential ?? candidate.appKey,
    };
  } catch {
    return null;
  }
}

export function setStoredSession(session: StoredSession) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

export function clearStoredSession() {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.removeItem(SESSION_STORAGE_KEY);
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT));
}

export function hasStoredSession(): boolean {
  return Boolean(getStoredSession());
}

export function useStoredSession(): StoredSession | null {
  const [session, setSession] = useState<StoredSession | null>(() => getStoredSession());

  useEffect(() => {
    const syncSession = () => {
      setSession(getStoredSession());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === SESSION_STORAGE_KEY) {
        syncSession();
      }
    };

    window.addEventListener(SESSION_CHANGE_EVENT, syncSession);
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener(SESSION_CHANGE_EVENT, syncSession);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  return session;
}
