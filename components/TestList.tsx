import type { StepResult, TestWithResult } from "@/lib/types";
import { evidenceSrc } from "@/lib/api";
import GeneratedByBadge from "./GeneratedByBadge";

export default function TestList({ tests }: { tests: TestWithResult[] }) {
  if (tests.length === 0) return <p className="empty">No tests yet. The Tester writes them after exploring.</p>;
  return (
    <div className="stack">
      {tests.map(({ test_case: tc, result }) => {
        const byIndex = new Map<number, StepResult>((result?.step_results ?? []).map((s) => [s.step_index, s]));
        const status = result?.status ?? "not run";
        return (
          <details key={tc.id} className="panel" open={result?.status === "failed" || result?.status === "error"}>
            <summary className="row">
              <strong>{tc.title}</strong>
              <span className="row gap">
                <span className={`badge test-${status.replace(" ", "-")}`}>{status}</span>
                <GeneratedByBadge value={tc.generated_by} />
              </span>
            </summary>
            {tc.expected_result && <p className="muted">Expected: {tc.expected_result}</p>}
            {result?.error_message && <p className="error">{result.error_message}</p>}
            <ol className="steps">
              {tc.steps.map((s) => {
                const r = byIndex.get(s.index);
                const shot = result?.evidence.find((e) => e.id === r?.evidence_id && e.kind === "screenshot");
                return (
                  <li key={s.index}>
                    <div className="row">
                      <span>{s.description ?? s.action} <span className="muted small">({s.action}{s.selector ? ` ${s.selector}` : ""})</span></span>
                      {r && <span className={`badge test-${r.status}`}>{r.status}</span>}
                    </div>
                    {r?.actual && <div className="muted small">Actual: {r.actual}</div>}
                    {r?.error_message && <div className="error small">{r.error_message}</div>}
                    {shot && (
                      <a href={evidenceSrc(shot.url)} target="_blank" rel="noreferrer" className="inline-shot">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={evidenceSrc(shot.url)} alt={shot.caption ?? "Screenshot at this step"} />
                      </a>
                    )}
                  </li>
                );
              })}
            </ol>
          </details>
        );
      })}
    </div>
  );
}
