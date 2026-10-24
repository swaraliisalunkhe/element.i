"use client";
import { useEffect, useRef } from "react";
import type { AgentEvent } from "@/lib/types";

export default function EventStream({ events, live, connectionLost }: { events: AgentEvent[]; live: boolean; connectionLost: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "nearest" }); }, [events.length]);
  return (
    <div className="panel stream" aria-live="polite">
      {events.length === 0 && <p className="empty">{live ? "Waiting for the agents to report progress..." : "No events were recorded for this run."}</p>}
      {events.map((e) => (
        <div key={e.seq} className={`thought agent-${e.agent} level-${e.level}`}>
          <div className="row gap">
            <span className="badge neutral">{e.agent}</span>
            <span className="muted small">{e.type.replace(/_/g, " ")}</span>
            <time className="muted small">{new Date(e.timestamp).toLocaleTimeString()}</time>
          </div>
          <p>{e.message}</p>
        </div>
      ))}
      {connectionLost && <p className="error">Live connection lost. Reconnecting...</p>}
      <div ref={end} />
    </div>
  );
}
