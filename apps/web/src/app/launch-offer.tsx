"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import styles from "./landing.module.css";

// Display only. The database campaign and per-account rules remain authoritative.
const OPENS_AT = Date.parse("2026-11-08T13:00:00Z");
const CLOSES_AT = Date.parse("2026-11-15T23:00:00Z");

export function LaunchOffer() {
  const [active, setActive] = useState(false);

  useEffect(() => {
    const sync = () => setActive(Date.now() >= OPENS_AT && Date.now() < CLOSES_AT);
    sync();
    const interval = window.setInterval(sync, 60_000);
    return () => window.clearInterval(interval);
  }, []);

  if (!active) return null;

  return (
    <section className={styles.offer} aria-labelledby="launch-offer-title">
      <div>
        <p className={styles.kicker}>LAUNCH INVITATION</p>
        <h2 id="launch-offer-title">Seven days of Pro. Your full seven days.</h2>
        <p>Eligible new accounts can explore Pro, while eligible existing Free workspace owners can claim in Plan &amp; Billing. Your 168 hours start when your trial activates. No card and no automatic charge.</p>
        <span className={styles.offerFootnote}>Enrollment closes November 15, 2026 at 11:59:59 PM WAT. Existing data remains available after a trial ends.</span>
      </div>
      <Link className={styles.primaryButton} href="/signup">Get started <span aria-hidden="true">↗</span></Link>
    </section>
  );
}
