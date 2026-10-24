"use client";
import type { BugReport } from "@/lib/types";
import { evidenceSrc } from "@/lib/api";

interface BugCardProps {
  bug: BugReport;
  defaultOpen?: boolean;
}

export default function BugCard({ bug, defaultOpen = false }: BugCardProps) {
  const shot = bug.evidence.find((e) => e.kind === "screenshot");
  const shotSrc = shot ? evidenceSrc(shot.url) : null;

  return (
    <details className={`bug ${bug.severity}`} open={defaultOpen || bug.severity === "critical"}>
      <summary>
        <span className={`chip sev-${bug.severity}`}>{bug.severity}</span>
        {bug.title}
        <span className="cat">{bug.category.replace(/_/g, " ")}</span>
      </summary>
      <div className="bd">
        {bug.steps_to_reproduce.length > 0 && (
          <div>
            <h5>Steps to reproduce</h5>
            <ol>
              {bug.steps_to_reproduce.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ol>
          </div>
        )}
        <div className="diff">
          <div className="e">
            <b>+ Expected</b>
            {bug.expected_behavior}
          </div>
          <div className="a">
            <b>− Actual</b>
            {bug.actual_behavior}
          </div>
        </div>
        <div>
          <h5>Evidence</h5>
          {shotSrc ? (
            <a href={shotSrc} target="_blank" rel="noreferrer" title="Click to view full evidence">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={shotSrc} alt={shot?.caption ?? bug.title} className="ev" />
            </a>
          ) : (
            <svg className="ev" viewBox="0 0 320 150">
              <rect width="320" height="150" fill="var(--site)" />
              <rect width="320" height="16" fill="var(--sline)" />
              <rect x="100" y="38" width="120" height="82" rx="8" fill="var(--sitecard)" stroke="var(--sline)" />
              <rect x="112" y="54" width="96" height="12" rx="3" fill="var(--sline)" />
              <rect x="112" y="74" width="96" height="12" rx="3" fill="none" stroke="var(--cr)" strokeWidth="2" />
              <rect x="112" y="96" width="96" height="14" rx="3" fill="var(--cy)" />
            </svg>
          )}
        </div>
      </div>
    </details>
  );
}
