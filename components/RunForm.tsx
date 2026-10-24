"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";
import type { AgentMode, RunCreate } from "@/lib/types";

export default function RunForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [url, setUrl] = useState("https://qa-sample-app.onrender.com");
  const [mode, setMode] = useState<AgentMode>("mock");
  const [maxPages, setMaxPages] = useState("10");
  const [maxDepth, setMaxDepth] = useState("2");
  const [maxTests, setMaxTests] = useState("20");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inRange = (v: string, lo: number, hi: number) => /^\d+$/.test(v) && +v >= lo && +v <= hi;

  async function start() {
    setError(null);
    if (!/^https?:\/\//.test(url)) return setError("Enter a full URL starting with http:// or https://");
    if (!inRange(maxPages, 1, 50)) return setError("Max pages must be between 1 and 50.");
    if (!inRange(maxDepth, 1, 5)) return setError("Max depth must be between 1 and 5.");
    if (!inRange(maxTests, 1, 100)) return setError("Max tests must be between 1 and 100.");
    const payload: RunCreate = {
      target_url: url, agent_mode: mode,
      max_pages: +maxPages, max_depth: +maxDepth, max_tests: +maxTests,
    };
    if (name.trim()) payload.name = name.trim();
    setBusy(true);
    try {
      const run = await createRun(payload);
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the run.");
      setBusy(false);
    }
  }

  return (
    <div className="panel stack">
      <label className="field"><span>App URL</span>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-app.example" /></label>
      <label className="field"><span>Run name (optional)</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Smoke run on sample app" /></label>
      <label className="field"><span>Agent mode</span>
        <select value={mode} onChange={(e) => setMode(e.target.value as AgentMode)}>
          <option value="mock">Mock (generated fixtures, no real browser)</option>
          <option value="real">Real (agents drive a browser)</option>
        </select></label>
      <div className="three-col">
        <label className="field"><span>Max pages (1-50)</span><input inputMode="numeric" value={maxPages} onChange={(e) => setMaxPages(e.target.value)} /></label>
        <label className="field"><span>Max depth (1-5)</span><input inputMode="numeric" value={maxDepth} onChange={(e) => setMaxDepth(e.target.value)} /></label>
        <label className="field"><span>Max tests (1-100)</span><input inputMode="numeric" value={maxTests} onChange={(e) => setMaxTests(e.target.value)} /></label>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary" onClick={start} disabled={busy}>{busy ? "Starting..." : "Start test run"}</button>
    </div>
  );
}
