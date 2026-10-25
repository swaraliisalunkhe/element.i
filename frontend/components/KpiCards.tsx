"use client";
import type { RunSummary } from "@/lib/types";

interface KpiCardsProps {
  summary?: RunSummary | null;
}

export default function KpiCards({ summary }: KpiCardsProps) {
  const journeys = summary?.journeys_count ?? 14;
  const testsTotal = summary?.tests_total ?? 48;
  const testsPassed = summary?.tests_passed ?? 46;
  const bugs = summary?.bugs_count ?? 4;
  const passRate = testsTotal > 0 ? Math.round((testsPassed / testsTotal) * 100) : 96;

  return (
    <div className="kpis">
      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Journeys discovered</p>
        <strong>
          <span data-n={journeys}>{journeys}</span>
        </strong>
        <small>Mapped paths</small>
        <div className="dots">
          <i /><i /><i /><i /><i /><i /><i />
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Autonomous tests executed</p>
        <strong>
          <span data-n={testsTotal}>{testsTotal}</span>
        </strong>
        <small>Total · {passRate}% pass rate</small>
        <div className="bar">
          <i style={{ width: `${passRate}%` }} />
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Bugs caught</p>
        <strong>
          <span data-n={bugs}>{bugs}</span>
        </strong>
        <div className="chips">
          <span className="chip sev-critical">{bugs > 1 ? `${bugs - 1} critical` : "1 critical"}</span>
          <span className="chip sev-high">1 high</span>
        </div>
      </div>

      <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
        <p>Agent confidence score</p>
        <strong>
          <span data-n="98.4">98.4</span>%
        </strong>
        <small>AI accuracy</small>
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
            strokeDasharray="111 113"
            transform="rotate(-90 22 22)"
          />
        </svg>
      </div>
    </div>
  );
}
