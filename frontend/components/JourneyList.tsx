import type { Journey } from "@/lib/types";
import GeneratedByBadge from "./GeneratedByBadge";

export default function JourneyList({ journeys }: { journeys: Journey[] }) {
  if (journeys.length === 0) return <p className="empty">No journeys yet. The Explorer is still mapping the app.</p>;
  return (
    <div className="stack">
      {journeys.map((j) => (
        <details key={j.id} className="panel">
          <summary className="row">
            <span><strong>{j.name}</strong> <span className="muted small">priority {j.priority}, {j.pages.length} pages</span></span>
            <GeneratedByBadge value={j.generated_by} />
          </summary>
          {j.description && <p>{j.description}</p>}
          <p className="muted small">Starts at {j.start_url}</p>
          {j.pages.map((p) => (
            <div key={p.url} className="page-block">
              <strong>{p.title ?? p.url}</strong> <span className="muted small">{p.url} (depth {p.depth})</span>
              <ul className="elements">
                {p.elements.map((el) => (
                  <li key={el.selector}>
                    <span className="badge neutral">{el.element_type}</span> {el.label ?? el.selector}
                    <span className="muted small"> {el.selector}{el.required ? " (required)" : ""}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </details>
      ))}
    </div>
  );
}
