"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { ApiError, useApi } from "@/lib/api";
import { Spinner } from "@/components/ui";
import type { Me } from "@/lib/types";

/** Routes the signed-in user: no company -> onboarding, else dashboard. */
export default function Home() {
  const api = useApi();
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    api
      .get<Me>("/me")
      .then(() => {
        if (!cancelled) router.replace("/dashboard");
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

  return <Spinner />;
}
