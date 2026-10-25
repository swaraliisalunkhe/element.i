"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import type { AgentEvent, Run } from "@/lib/types";

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
  isInteractiveRun = false,
}: LiveViewportProps) {
  const urlDisplay = (targetUrl ?? run?.target_url ?? "https://code-apex-sample-app-v2.onrender.com/").replace(/\/$/, "");

  const [emailText, setEmailText] = useState("");
  const [passwordText, setPasswordText] = useState("");
  const [isDone, setIsDone] = useState(false);
  const [alertOn, setAlertOn] = useState(false);
  const [bbox, setBbox] = useState<{ on: boolean; bad: boolean; selector: string; style: React.CSSProperties }>({
    on: false,
    bad: false,
    selector: "",
    style: {},
  });
  const [aiPos, setAiPos] = useState({ x: 20, y: 20, click: false });

  const stageRef = useRef<HTMLDivElement>(null);

  // Sync with live event stream or sequence
  const seq = latestEvent?.seq ?? (events.length > 0 ? events[events.length - 1].seq : 0);

  useEffect(() => {
    if (seq >= 5 || latestEvent?.type === "bug_reported" || latestEvent?.type === "run_completed") {
      setIsDone(true);
      setAlertOn(true);
      setBbox({
        on: true,
        bad: true,
        selector: "#error-message",
        style: { left: "20%", top: "30%", width: "60%", height: "45%" },
      });
      setAiPos({ x: 190, y: 120, click: false });
      return;
    }

    if (seq === 4 || latestEvent?.type === "test_completed") {
      setEmailText("user@example.com");
      setPasswordText("");
      setIsDone(true);
      setAlertOn(true);
      setBbox({
        on: true,
        bad: true,
        selector: "button[type='submit']",
        style: { left: "30%", top: "58%", width: "40%", height: "34px" },
      });
      setAiPos({ x: 170, y: 145, click: true });
      return;
    }

    if (seq === 3 || latestEvent?.agent === "tester") {
      setEmailText("user@example.com");
      setPasswordText("");
      setIsDone(false);
      setAlertOn(false);
      setBbox({
        on: true,
        bad: false,
        selector: "#email",
        style: { left: "30%", top: "32%", width: "40%", height: "30px" },
      });
      setAiPos({ x: 165, y: 88, click: false });
      return;
    }

    if (seq >= 1) {
      setEmailText("");
      setPasswordText("");
      setIsDone(false);
      setAlertOn(false);
      setBbox({
        on: true,
        bad: false,
        selector: "#email",
        style: { left: "30%", top: "32%", width: "40%", height: "30px" },
      });
      setAiPos({ x: 120, y: 50, click: false });
      return;
    }

    // Default reset
    setEmailText("");
    setPasswordText("");
    setIsDone(false);
    setAlertOn(false);
    setBbox({ on: false, bad: false, selector: "", style: {} });
    setAiPos({ x: 20, y: 20, click: false });
  }, [seq, latestEvent]);

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
          <span id="addr">{urlDisplay}</span>
        </div>
        <span className="radar">
          <b />
          {live ? "LIVE" : "DONE"}
        </span>
      </div>

      <div className={`stage ${isDone ? "done" : ""}`} id="stage" ref={stageRef}>
        <div className="nav">
          <b />
          <span />
          <span />
          <span />
        </div>

        <div className="site">
          <div className="form">
            <h4>Welcome back</h4>
            <label>Email</label>
            <div className="fld" id="email">
              {emailText}
            </div>
            <label>Password</label>
            <div className="fld" id="password">
              {passwordText}
            </div>
            <div className="sbtn" id="submit">
              Sign in
            </div>
          </div>

          <div className="welcome">
            <h4>Dashboard</h4>
            <p id="who">Welcome, user@example.com</p>
          </div>
        </div>

        {/* Animated Bounding Box */}
        <div
          className={`bbox ${bbox.on ? "on" : ""} ${bbox.bad ? "bad" : ""}`}
          id="bb"
          style={bbox.style}
          data-s={bbox.selector}
        />

        {/* Floating AI Virtual Cursor */}
        <svg
          className={`ai ${aiPos.click ? "click" : ""}`}
          id="ai"
          viewBox="0 0 24 24"
          fill="currentColor"
          style={{ transform: `translate(${aiPos.x}px, ${aiPos.y}px)` }}
        >
          <path d="M3 2l7 19 3-8 8-3z" />
        </svg>

        {/* Critical Alert Banner */}
        <div className={`alert ${alertOn ? "on" : ""}`} id="al">
          <b>Critical</b>
          <span>Login accepted an empty password and opened the dashboard.</span>
        </div>
      </div>
    </section>
  );
}
