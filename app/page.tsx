"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import type { Run } from "@/lib/types";
import { listRuns } from "@/lib/api";
import RunForm from "@/components/RunForm";
import RunStatusBadge from "@/components/RunStatusBadge";

export default function Home() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns().then(setRuns).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="stack gap-lg">
      <section><h1>Test a web app</h1><RunForm /></section>
      <section className="stack">
        <h2>Recent runs</h2>
        {error && <p className="error" role="alert">{error}</p>}
        {!runs && !error && <p className="muted">Loading runs...</p>}
        {runs && runs.length === 0 && <p className="empty">No runs yet. Start one above.</p>}
        {runs?.map((r) => (
          <Link key={r.id} href={`/runs/${r.id}`} className="panel run-row">
            <div><strong>{r.name ?? r.target_url}</strong><div className="muted">{r.target_url} | {r.agent_mode}</div></div>
            <div className="row gap">
              {r.summary && <span className="muted">{r.summary.bugs_count} bugs</span>}
              <RunStatusBadge status={r.status} />
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
