"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { AgentEvent, BugReport, Journey, Run, TestWithResult } from "@/lib/types";
import { getBugs, getJourneys, getRun, getTests, subscribeRunEvents } from "@/lib/api";
import LiveViewport from "@/components/LiveViewport";
import EventStream from "@/components/EventStream";
import KpiCards from "@/components/KpiCards";
import BugList from "@/components/BugList";
import TestList from "@/components/TestList";

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [journeys, setJourneys] = useState<Journey[]>([]);
  const [tests, setTests] = useState<TestWithResult[]>([]);
  const [bugs, setBugs] = useState<BugReport[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lost, setLost] = useState(false);
  const [streamDone, setStreamDone] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, j, t, b] = await Promise.all([getRun(id), getJourneys(id), getTests(id), getBugs(id)]);
      setRun(r);
      setJourneys(j);
      setTests(t);
      setBugs(b);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this run.");
    }
  }, [id]);

  const loadSoon = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(load, 400);
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setEvents([]);
    setStreamDone(false);
    setLost(false);
    const stop = subscribeRunEvents(id, {
      onEvent: (e) => {
        setEvents((prev) => (prev.some((p) => p.seq === e.seq) ? prev : [...prev, e].sort((a, b) => a.seq - b.seq)));
        loadSoon();
      },
      onEnd: () => {
        setStreamDone(true);
        setLost(false);
        load();
      },
      onConnectionLost: () => setLost(true),
      onConnectionRestored: () => setLost(false),
    });
    return () => {
      stop();
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id, load, loadSoon]);

  if (error && !run) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center" }}>
        <p className="err" role="alert">
          {error}
        </p>
        <Link href="/" className="go" style={{ display: "inline-block", marginTop: "16px" }}>
          ← Return to Console
        </Link>
      </div>
    );
  }

  if (!run) {
    return (
      <div style={{ padding: "80px 0", textAlign: "center", color: "var(--mu)" }}>
        <span className="live">
          <b />
          Connecting to run telemetry...
        </span>
      </div>
    );
  }

  const live = !streamDone && run.status !== "completed" && run.status !== "failed";

  return (
    <>
      {/* Top Header Navigation */}
      <header className="top">
        <Link href="/" style={{ color: "inherit", textDecoration: "none", display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontWeight: 700, fontSize: "1.2rem", letterSpacing: "-0.03em" }}>
            element<span style={{ color: "var(--cy)" }}>.</span>i
          </span>
          <span style={{ color: "var(--mu)", fontSize: "0.85rem" }}>/ telemetry</span>
        </Link>
        <div className="tr">
          <Link href="/" className="mo">
            ← New QA Run
          </Link>
        </div>
      </header>

      {/* Run Summary Banner */}
      <div className="card" style={{ padding: "16px 20px", marginTop: "10px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <h2 style={{ margin: "0 0 4px", fontSize: "1.4rem", letterSpacing: "-0.02em" }}>
              {run.name ?? run.target_url}
            </h2>
            <div style={{ color: "var(--mu)", fontSize: "13px" }}>
              Target: <code>{run.target_url}</code> | Mode: <strong>{run.agent_mode}</strong>
            </div>
          </div>
          <div>
            <span
              className={`pill ${
                run.status === "completed"
                  ? "p-c"
                  : run.status === "testing"
                  ? "p-t"
                  : run.status === "exploring"
                  ? "p-e"
                  : "p-q"
              }`}
            >
              <b />
              {run.status.toUpperCase()}
            </span>
          </div>
        </div>
        {run.status === "failed" && (
          <p className="err" style={{ marginTop: "10px", textAlign: "left" }}>
            This run failed{run.error_message ? `: ${run.error_message}` : "."}
          </p>
        )}
      </div>

      {/* Main Execution Dashboard */}
      <div className="dash" style={{ marginTop: "20px" }}>
        <div className="main">
          {/* Left Column: Live Viewport & Agent Feed */}
          <div className="col">
            <LiveViewport
              run={run}
              latestEvent={events[events.length - 1]}
              events={events}
              live={live}
              targetUrl={run.target_url}
            />

            <EventStream
              events={events}
              live={live}
              connectionLost={lost}
              modeLabel={run.agent_mode === "real" ? "Real browser" : "Mock agent: generated fixtures"}
            />
          </div>

          {/* Right Column: KPIs & Bugs/Journeys */}
          <div className="col">
            <KpiCards summary={run.summary} bugs={bugs} tests={tests} journeys={journeys} />

            <BugList bugs={bugs} journeys={journeys} />
          </div>
        </div>

        {/* Detailed Test Cases Section */}
        {tests.length > 0 && (
          <section className="card" style={{ marginTop: "20px", padding: "16px 20px" }}>
            <div className="hd" style={{ padding: "0 0 12px", borderBottom: "1px solid var(--bd)" }}>
              Test Execution Breakdown <small>{tests.length} tests</small>
            </div>
            <div style={{ marginTop: "14px" }}>
              <TestList tests={tests} />
            </div>
          </section>
        )}
      </div>
    </>
  );
}
