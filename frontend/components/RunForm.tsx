"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createRun } from "@/lib/api";
import type { AgentMode, RunCreate } from "@/lib/types";

interface RunFormProps {
  onLaunch?: (url: string, mode: AgentMode, depth: number, pages: number) => void;
  initialUrl?: string;
}

export default function RunForm({ onLaunch, initialUrl }: RunFormProps) {
  const router = useRouter();
  const [url, setUrl] = useState(initialUrl ?? "");
  const [mode, setMode] = useState<AgentMode>("real");
  const [maxDepth, setMaxDepth] = useState(2);
  const [maxPages, setMaxPages] = useState(10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function adjustDepth(delta: number) {
    setMaxDepth((prev) => Math.max(1, Math.min(5, prev + delta)));
  }

  function adjustPages(delta: number) {
    setMaxPages((prev) => Math.max(1, Math.min(50, prev + delta)));
  }

  async function handleLaunch() {
    setError(null);
    const target = url.trim() || "https://code-apex-sample-app-v2.onrender.com/";

    if (!/^https?:\/\/\S+\.\S+/.test(target)) {
      setError("Enter a full URL starting with http:// or https://");
      return;
    }

    if (onLaunch) {
      onLaunch(target, mode, maxDepth, maxPages);
      return;
    }

    setBusy(true);
    const payload: RunCreate = {
      target_url: target,
      agent_mode: mode,
      max_depth: maxDepth,
      max_pages: maxPages,
      max_tests: 20,
    };

    try {
      const run = await createRun(payload);
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not launch QA Swarm.");
      setBusy(false);
    }
  }

  return (
    <div className="console">
      <div className="omni">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18" />
        </svg>

        <input
          id="url"
          type="url"
          inputMode="url"
          autoComplete="off"
          aria-label="Target URL"
          placeholder="https://your-web-app.com — enter target URL to dispatch QA agents"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleLaunch();
          }}
        />

        <button
          type="button"
          className="go"
          id="go"
          onClick={handleLaunch}
          disabled={busy}
        >
          {busy ? "Dispatching..." : "Launch QA Swarm ⚡"}
        </button>
      </div>

      <div className="pills">
        <span className="seg" role="group" aria-label="Agent mode">
          <button
            type="button"
            aria-pressed={mode === "real"}
            onClick={() => setMode("real")}
          >
            Real Browser
          </button>
          <button
            type="button"
            aria-pressed={mode === "mock"}
            onClick={() => setMode("mock")}
          >
            Mock Agent
          </button>
        </span>

        <span className="step">
          Max depth{" "}
          <button
            type="button"
            aria-label="Decrease depth"
            onClick={() => adjustDepth(-1)}
          >
            −
          </button>
          <output id="depth">{maxDepth}</output>
          <button
            type="button"
            aria-label="Increase depth"
            onClick={() => adjustDepth(1)}
          >
            +
          </button>
        </span>

        <span className="step">
          Max pages{" "}
          <button
            type="button"
            aria-label="Decrease pages"
            onClick={() => adjustPages(-5)}
          >
            −
          </button>
          <output id="pages">{maxPages}</output>
          <button
            type="button"
            aria-label="Increase pages"
            onClick={() => adjustPages(5)}
          >
            +
          </button>
        </span>

        {error && (
          <p className="err" id="err" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
