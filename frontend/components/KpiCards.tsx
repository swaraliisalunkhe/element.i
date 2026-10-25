"use client";
import type { BugReport, Journey, RunSummary, TestWithResult } from "@/lib/types";

interface KpiCardsProps {
  summary?: RunSummary | null;
  bugs?: BugReport[];
  tests?: TestWithResult[];
  journeys?: Journey[];
}

export default function KpiCards({ summary, bugs = [], tests = [], journeys = [] }: KpiCardsProps) {
  const journeysCount = summary?.journeys_count ?? journeys.length;
  const testsTotal = summary?.tests_total ?? tests.length;
  const testsPassed = summary?.tests_passed ?? tests.filter((t) => t.result?.status === "passed").length;
  const bugsCount = summary?.bugs_count ?? bugs.length;
  const passRate = testsTotal > 0 ? Math.round((testsPassed / testsTotal) * 100) : null;

  const criticalBugs = bugs.filter((b) => b.severity === "critical").length;
  const highBugs = bugs.filter((b) => b.severity === "high").length;
  const otherBugs = bugsCount - criticalBugs - highBugs;

  const confidences = bugs
    .map((b) => b.confidence)
    .filter((c): c is number => typeof c === "number" && !isNaN(c));
  const avgConfidence = confidences.length > 0
    ? Math.round((confidences.reduce((acc, val) => acc + val, 0) / confidences.length) * 1000) / 10
    : null;

  return (
    <div className="kpis">
      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Journeys discovered</p>
        <strong>
          <span data-n={journeysCount}>{journeysCount}</span>
        </strong>
        <small>{journeysCount > 0 ? "Mapped paths" : "No journeys yet"}</small>
        <div className="dots">
          <i /><i /><i /><i /><i /><i /><i />
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Autonomous tests executed</p>
        <strong>
          <span data-n={testsTotal}>{testsTotal}</span>
        </strong>
        <small>
          {testsTotal > 0 ? `Total · ${passRate}% pass rate` : "Total · No tests run yet"}
        </small>
        <div className="bar">
          <i style={{ width: passRate !== null ? `${passRate}%` : "0%" }} />
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Bugs caught</p>
        <strong>
          <span data-n={bugsCount}>{bugsCount}</span>
        </strong>
        <div className="chips">
          {bugsCount === 0 ? (
            <small style={{ color: "var(--mu)", fontSize: "12px" }}>No bugs detected</small>
          ) : (
            <>
              {criticalBugs > 0 && <span className="chip sev-critical">{criticalBugs} critical</span>}
              {highBugs > 0 && <span className="chip sev-high">{highBugs} high</span>}
              {otherBugs > 0 && <span className="chip sev-medium">{otherBugs} medium/low</span>}
            </>
          )}
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Agent confidence score</p>
        <strong>
          {avgConfidence !== null ? (
            <>
              <span data-n={avgConfidence}>{avgConfidence}</span>%
            </>
          ) : (
            <span>No data yet</span>
          )}
        </strong>
        <small>{avgConfidence !== null ? "Avg bug confidence" : "Awaiting test results"}</small>
        <svg className="gauge" width="44" height="44" viewBox="0 0 44 44">
          <circle cx="22" cy="22" r="18" fill="none" stroke="var(--card2)" strokeWidth="5" />
          <circle
            cx="22"
            cy="22"
            r="18"
            fill="none"
            stroke="var(--cy)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeDasharray={`${avgConfidence !== null ? Math.round((avgConfidence / 100) * 113) : 0} 113`}
            transform="rotate(-90 22 22)"
          />
        </svg>
      </div>
    </div>
  );
}
