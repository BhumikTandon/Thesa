"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useMemo, useRef } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    detail: string,
  ) {
    super(detail);
  }
}

/** Bearer-token fetch wrapper bound to the caller's Clerk session. */
export function useApi() {
  const { getToken } = useAuth();

  // Read getToken through a ref so `request` (and the returned object) stay
  // referentially stable even if Clerk hands back a new function per render.
  const getTokenRef = useRef(getToken);
  useEffect(() => {
    getTokenRef.current = getToken;
  }, [getToken]);

  const request = useCallback(
    async <T>(path: string, init?: RequestInit): Promise<T> => {
      const token = await getTokenRef.current();
      const response = await fetch(`${API_URL}${path}`, {
        ...init,
        cache: "no-store",
        headers: {
          Authorization: `Bearer ${token}`,
          ...(init?.body ? { "Content-Type": "application/json" } : {}),
          ...init?.headers,
        },
      });
      if (!response.ok) {
        let detail = `Request failed (${response.status})`;
        try {
          const body = await response.json();
          if (typeof body.detail === "string") detail = body.detail;
        } catch {
          // non-JSON error body; keep default detail
        }
        throw new ApiError(response.status, detail);
      }
      return response.json() as Promise<T>;
    },
    [],
  );

  // Memoized so the returned object is referentially stable across renders.
  // Pages use it as an effect dependency; a fresh object per render would
  // retrigger effects after every state update — an infinite fetch loop.
  return useMemo(
    () => ({
      get: <T>(path: string) => request<T>(path),
      post: <T>(path: string, body?: unknown) =>
        request<T>(path, {
          method: "POST",
          body: body === undefined ? undefined : JSON.stringify(body),
        }),
      patch: <T>(path: string, body: unknown) =>
        request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
    }),
    [request],
  );
}
