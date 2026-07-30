"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, useApi } from "@/lib/api";
import { Spinner } from "@/components/ui";
import type { Me } from "@/lib/types";

const MeContext = createContext<Me | null>(null);

export function useMe(): Me {
  const me = useContext(MeContext);
  if (!me) throw new Error("useMe must be used inside MeProvider");
  return me;
}

export function useIsManager(): boolean {
  const me = useMe();
  return me.role === "owner" || me.role === "office_manager";
}

/** Loads the caller's identity; bounces company-less users to onboarding. */
export function MeProvider({ children }: { children: React.ReactNode }) {
  const api = useApi();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<Me>("/me")
      .then((data) => {
        if (!cancelled) setMe(data);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 403) {
          router.replace("/onboarding");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api, router]);

  if (!me) return <Spinner />;
  return <MeContext.Provider value={me}>{children}</MeContext.Provider>;
}
