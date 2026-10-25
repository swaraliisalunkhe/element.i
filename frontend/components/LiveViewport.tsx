"use client";
import { useEffect, useRef } from "react";
import type { AgentEvent, Run } from "@/lib/types";
import { evidenceSrc } from "@/lib/api";

interface LiveViewportProps {
  run?: Run | null;
  latestEvent?: AgentEvent;
  events?: AgentEvent[];
  live?: boolean;
  targetUrl?: string;
  isInteractiveRun?: boolean;
}

export default function LiveViewport({
  run,
  latestEvent,
  events = [],
  live = true,
  targetUrl,
}: LiveViewportProps) {
  const currentUrl =
    (latestEvent?.data?.url as string) ||
    (latestEvent?.data?.current_url as string) ||
    targetUrl ||
    run?.target_url ||
    "https://code-apex-sample-app-v2.onrender.com/";

  // Look for latest screenshot evidence across recent events
  const latestScreenshot = (() => {
    if (latestEvent?.data?.screenshot_url) {
      return String(latestEvent.data.screenshot_url);
    }
    for (let i = events.length - 1; i >= 0; i--) {
      const url = events[i].data?.screenshot_url;
      if (url) return String(url);
    }
    return null;
  })();

  const activeSelector = latestEvent?.data?.selector ? String(latestEvent.data.selector) : null;
  const isBugReported = latestEvent?.type === "bug_reported";
  const agentName = latestEvent?.agent || (live ? "orchestrator" : "system");

  return (
    <section className="card">
      <div className="chrome">
        <i />
        <i />
        <i />
        <div className="addr">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 10V8a5 5 0 0110 0v2h1a1 1 0 011 1v9a1 1 0 01-1 1H6a1 1 0 01-1-1v-9a1 1 0 011-1h1zm2 0h6V8a3 3 0 00-6 0v2z" />
          </svg>
          <span id="addr">{currentUrl}</span>
        </div>
        <span className="radar">
          <b />
          {live ? "LIVE" : "DONE"}
        </span>
      </div>

      <div className="stage" id="stage" style={{ minHeight: "260px", position: "relative", overflow: "hidden" }}>
        {latestScreenshot ? (
          <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={evidenceSrc(latestScreenshot)}
              alt="Live browser screenshot"
              style={{ maxWidth: "100%", maxHeight: "320px", objectFit: "contain", borderRadius: "4px" }}
            />
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              padding: "36px 20px",
              height: "100%",
              textAlign: "center",
              gap: "12px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span className={`tag t-${agentName}`} style={{ textTransform: "uppercase", fontWeight: 700 }}>
                {agentName}
              </span>
              <span style={{ fontSize: "12px", color: "var(--mu)" }}>
                {live ? "Browser Automation Active" : "Run Finished"}
              </span>
            </div>

            <p style={{ margin: "4px 0", fontSize: "14px", fontWeight: 500, maxWidth: "480px" }}>
              {latestEvent?.message || (live ? "Initializing browser driver..." : "Execution completed.")}
            </p>

            {activeSelector && (
              <div style={{ fontSize: "12px", color: "var(--cy)", fontFamily: "monospace", background: "var(--card2)", padding: "4px 8px", borderRadius: "4px" }}>
                Target: {activeSelector}
              </div>
            )}
          </div>
        )}

        {isBugReported && (
          <div className="alert on" id="al">
            <b>{String(latestEvent?.data?.severity || "Bug Reported").toUpperCase()}</b>
            <span>{latestEvent?.message || "Anomaly detected by test agent."}</span>
          </div>
        )}
      </div>
    </section>
  );
}
