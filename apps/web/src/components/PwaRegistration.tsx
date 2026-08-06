"use client";

import { useEffect } from "react";

export function PwaRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) {
      return;
    }

    navigator.serviceWorker.register("/sw.js").catch(() => {
      // PWA support is progressive enhancement; a registration failure must
      // never prevent the authenticated web application from working.
    });
  }, []);

  return null;
}
