"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import type { AgentEvent, BugReport, Journey, Run, TestWithResult } from "@/lib/types";
import { getBugs, getJourneys, getRun, getTests, subscribeRunEvents } from "@/lib/api";
import RunStatusBadge from "@/components/RunStatusBadge";
import JourneyList from "@/components/JourneyList";
import TestList from "@/components/TestList";
import BugList from "@/components/BugList";
import EventStream from "@/components/EventStream";
import LiveViewport from "@/components/LiveViewport";

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
      setRun(r); setJourneys(j); setTests(t); setBugs(b); setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load this run.");
    }
  }, [id]);

  const loadSoon = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(load, 400);
  }, [load]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    setEvents([]); setStreamDone(false); setLost(false);
    const stop = subscribeRunEvents(id, {
      onEvent: (e) => {
        setEvents((prev) => (prev.some((p) => p.seq === e.seq) ? prev : [...prev, e].sort((a, b) => a.seq - b.seq)));
        loadSoon();
      },
      onEnd: () => { setStreamDone(true); setLost(false); load(); },
      onConnectionLost: () => setLost(true),
      onConnectionRestored: () => setLost(false),
    });
    return () => { stop(); if (timer.current) clearTimeout(timer.current); };
  }, [id, load, loadSoon]);

  if (error && !run) return <p className="error" role="alert">{error}</p>;
  if (!run) return <p className="muted">Loading run...</p>;

  const live = !streamDone && run.status !== "completed" && run.status !== "failed";
  const s = run.summary;

  return (
    <div className="stack gap-lg">
      <section className="stack">
        <div className="row"><h1>{run.name ?? run.target_url}</h1><RunStatusBadge status={run.status} /></div>
        <p className="muted">{run.target_url} | agent mode: {run.agent_mode}</p>
        {run.agent_mode === "mock" && (
          <p className="notice" role="note">
            Mock run: every journey, test and bug here is a generated fixture, and screenshots are grey placeholders, not real captures.
          </p>
        )}
        {s && (
          <p className="muted">
            {s.journeys_count} journeys | {s.tests_total} tests ({s.tests_passed} passed, {s.tests_failed} failed) | {s.bugs_count} bugs
          </p>
        )}
        {run.status === "failed" && <p className="error">This run failed{run.error_message ? `: ${run.error_message}` : "."}</p>}
        {error && <p className="error" role="alert">{error}</p>}
      </section>
      <section className="stack">
        <h2>Live Agent Execution &amp; Target Viewport</h2>
        <div className="live-view-grid">
          <LiveViewport
            run={run}
            latestEvent={events[events.length - 1]}
            events={events}
            tests={tests}
            live={live}
          />
          <div className="live-stream-column">
            <h3 style={{ margin: "0 0 4px" }}>Agent Activity Log</h3>
            <EventStream events={events} live={live} connectionLost={lost} />
          </div>
        </div>
      </section>
      <section className="stack"><h2>Journeys</h2><JourneyList journeys={journeys} /></section>
      <section className="stack"><h2>Tests</h2><TestList tests={tests} /></section>
      <section className="stack"><h2>Bugs</h2><BugList bugs={bugs} /></section>
    </div>
  );
}
