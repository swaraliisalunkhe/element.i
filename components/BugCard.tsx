import type { BugReport } from "@/lib/types";
import { evidenceSrc } from "@/lib/api";
import GeneratedByBadge from "./GeneratedByBadge";

export default function BugCard({ bug }: { bug: BugReport }) {
  const shots = bug.evidence.filter((e) => e.kind === "screenshot");
  return (
    <article className={`panel bug sev-${bug.severity}`}>
      <header className="row">
        <h3>{bug.title}</h3>
        <span className="row gap">
          <span className={`badge sev-${bug.severity}`}>{bug.severity}</span>
          <span className="badge neutral">{bug.category.replace(/_/g, " ")}</span>
          <GeneratedByBadge value={bug.generated_by} />
        </span>
      </header>
      {bug.description && <p>{bug.description}</p>}
      <h4>Steps to reproduce</h4>
      <ol>{bug.steps_to_reproduce.map((s, i) => <li key={i}>{s}</li>)}</ol>
      <div className="two-col">
        <div><h4>Expected</h4><p>{bug.expected_behavior}</p></div>
        <div><h4>Actual</h4><p>{bug.actual_behavior}</p></div>
      </div>
      <p className="muted small">
        {bug.page_url && <>Page: {bug.page_url}</>}
        {bug.confidence !== null && <>{bug.page_url ? " | " : ""}Confidence: {Math.round(bug.confidence * 100)}%</>}
      </p>
      {shots.length > 0 && (
        <div className="shots">
          {shots.map((e) => (
            <a key={e.id} href={evidenceSrc(e.url)} target="_blank" rel="noreferrer">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={evidenceSrc(e.url)} alt={e.caption ?? "Screenshot of the failure"} />
              {e.caption && <span>{e.caption}</span>}
            </a>
          ))}
        </div>
      )}
    </article>
  );
}
