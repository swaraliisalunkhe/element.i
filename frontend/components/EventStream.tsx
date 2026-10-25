"use client";
import { useEffect, useRef } from "react";
import type { AgentEvent } from "@/lib/types";

interface EventStreamProps {
  events: AgentEvent[];
  live?: boolean;
  connectionLost?: boolean;
  modeLabel?: string;
}

export default function EventStream({
  events,
  live = true,
  connectionLost = false,
  modeLabel = "Real browser",
}: EventStreamProps) {
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [events.length]);

  return (
    <section className="card">
      <div className="hd">
        Agent thought stream <small id="modeNote">{modeLabel}</small>
      </div>
      <div className="feed" id="feed" aria-live="polite">
        {events.length === 0 && (
          <div>
            <time>{new Date().toLocaleTimeString([], { hour12: false })}</time>
            <span className="tag t-orchestrator">orchestrator</span>
            <span>{live ? "Waiting for agents to dispatch..." : "No events recorded."}</span>
          </div>
        )}

        {events.map((e) => (
          <div key={e.id || e.seq}>
            <time>
              {new Date(e.timestamp).toLocaleTimeString([], { hour12: false })}
            </time>
            <span className={`tag t-${e.agent}`}>{e.agent}</span>
            <span>{e.message}</span>
          </div>
        ))}

        {live && <div className="caret" />}
        {connectionLost && (
          <div style={{ color: "var(--cr)" }}>
            <time>!</time>
            <span className="tag t-orchestrator">system</span>
            <span>Live connection interrupted. Reconnecting...</span>
          </div>
        )}
        <div ref={end} />
      </div>
    </section>
  );
}
