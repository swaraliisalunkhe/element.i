"use client";
import { useMemo, useState } from "react";
import type { AgentEvent, AgentName, Run, TestWithResult } from "@/lib/types";
import { evidenceSrc } from "@/lib/api";

interface LiveViewportProps {
  run: Run;
  latestEvent?: AgentEvent;
  events: AgentEvent[];
  tests: TestWithResult[];
  live: boolean;
}

interface StepSimState {
  url: string;
  pageTitle: string;
  activeSelector?: string;
  actionText?: string;
  cursorPos?: { x: number; y: number };
  cursorVisible: boolean;
  fieldEmailValue: string;
  fieldPasswordValue: string;
  pageRoute: "home" | "login" | "dashboard";
  isBugTriggered?: boolean;
}

export default function LiveViewport({ run, latestEvent, events, tests, live }: LiveViewportProps) {
  const [viewMode, setViewMode] = useState<"agent" | "iframe">("agent");
  const [copied, setCopied] = useState(false);

  // Determine current active agent
  const currentAgent: AgentName = latestEvent?.agent ?? "orchestrator";

  // Derive simulation state from incoming events / latest test steps
  const simState = useMemo<StepSimState>(() => {
    const seq = latestEvent?.seq ?? 0;
    const targetUrl = run.target_url.replace(/\/$/, "");

    // Determine current phase based on event sequence or type
    if (seq >= 5 || latestEvent?.type === "bug_reported" || latestEvent?.type === "run_completed") {
      return {
        url: `${targetUrl}/dashboard`,
        pageTitle: "Dashboard (Unauthorized Access)",
        activeSelector: "#error-message",
        actionText: "Assert failed: Expected validation error, but page redirected to /dashboard",
        cursorPos: { x: 50, y: 35 },
        cursorVisible: true,
        fieldEmailValue: "user@example.com",
        fieldPasswordValue: "",
        pageRoute: "dashboard",
        isBugTriggered: true,
      };
    }

    if (seq === 4 || latestEvent?.type === "test_completed") {
      return {
        url: `${targetUrl}/login`,
        pageTitle: "Log In - Submitting form",
        activeSelector: "button[type='submit']",
        actionText: "Clicking 'Sign in' with empty password field",
        cursorPos: { x: 50, y: 68 },
        cursorVisible: true,
        fieldEmailValue: "user@example.com",
        fieldPasswordValue: "",
        pageRoute: "login",
        isBugTriggered: false,
      };
    }

    if (seq === 3 || latestEvent?.message?.toLowerCase().includes("tester")) {
      return {
        url: `${targetUrl}/login`,
        pageTitle: "Log In - Entering Credentials",
        activeSelector: "#email",
        actionText: "Typing into #email: 'user@example.com'",
        cursorPos: { x: 50, y: 45 },
        cursorVisible: true,
        fieldEmailValue: "user@example.com",
        fieldPasswordValue: "",
        pageRoute: "login",
        isBugTriggered: false,
      };
    }

    if (seq === 2 || latestEvent?.type === "journey_discovered") {
      return {
        url: `${targetUrl}/login`,
        pageTitle: "Log In Page - Mapping Elements",
        activeSelector: "#email",
        actionText: "Explorer mapping DOM elements: #email, #password, submit button",
        cursorPos: { x: 48, y: 40 },
        cursorVisible: true,
        fieldEmailValue: "",
        fieldPasswordValue: "",
        pageRoute: "login",
        isBugTriggered: false,
      };
    }

    if (seq >= 1 || latestEvent?.type === "agent_started") {
      return {
        url: `${targetUrl}/`,
        pageTitle: "Home Page - Autonomous Crawl",
        activeSelector: "a[href='/login']",
        actionText: "Navigating to home page & discovering navigation links",
        cursorPos: { x: 80, y: 15 },
        cursorVisible: true,
        fieldEmailValue: "",
        fieldPasswordValue: "",
        pageRoute: "home",
        isBugTriggered: false,
      };
    }

    // Default initial state
    return {
      url: targetUrl,
      pageTitle: "Connecting to target application...",
      activeSelector: undefined,
      actionText: "Initializing QA agent session...",
      cursorPos: { x: 50, y: 50 },
      cursorVisible: false,
      fieldEmailValue: "",
      fieldPasswordValue: "",
      pageRoute: "home",
      isBugTriggered: false,
    };
  }, [latestEvent, run.target_url]);

  // Check if there is an image snapshot available in the latest test or evidence
  const latestScreenshot = useMemo(() => {
    for (let i = tests.length - 1; i >= 0; i--) {
      const shot = tests[i].result?.evidence.find((e) => e.kind === "screenshot");
      if (shot) return evidenceSrc(shot.url);
    }
    // Also check event data if real backend provided one
    if (latestEvent?.data && typeof latestEvent.data === "object") {
      const d = latestEvent.data as Record<string, unknown>;
      if (typeof d.screenshot_url === "string") return evidenceSrc(d.screenshot_url);
    }
    return null;
  }, [tests, latestEvent]);

  function copyUrl() {
    navigator.clipboard.writeText(simState.url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="panel viewport-panel">
      {/* Browser Window Chrome Top Header */}
      <div className="viewport-header">
        <div className="browser-window-dots" aria-hidden="true">
          <span className="dot dot-close" />
          <span className="dot dot-minimize" />
          <span className="dot dot-expand" />
        </div>

        {/* Browser Address Bar */}
        <div className="browser-address-bar">
          <span className="ssl-lock" title="Connection encrypted">🔒</span>
          <span className="browser-url-text" title={simState.url}>{simState.url}</span>
          <button
            type="button"
            className="browser-icon-btn"
            onClick={copyUrl}
            title={copied ? "Copied!" : "Copy URL"}
          >
            {copied ? "✓" : "📋"}
          </button>
          <a
            href={simState.url}
            target="_blank"
            rel="noreferrer"
            className="browser-icon-btn"
            title="Open website in new browser tab"
          >
            ↗
          </a>
        </div>

        {/* Viewport Meta & Mode Selector */}
        <div className="viewport-header-actions">
          <span className="viewport-dimensions">1280 × 720</span>
          <div className="viewport-toggle-group">
            <button
              type="button"
              className={`chip ${viewMode === "agent" ? "on" : ""}`}
              onClick={() => setViewMode("agent")}
              title="View the AI Agent's active screen and cursor"
            >
              Agent View
            </button>
            <button
              type="button"
              className={`chip ${viewMode === "iframe" ? "on" : ""}`}
              onClick={() => setViewMode("iframe")}
              title="Direct embedded web frame"
            >
              Direct Frame
            </button>
          </div>
        </div>
      </div>

      {/* Active Agent & Action Spotlight Banner */}
      <div className={`agent-activity-banner agent-${currentAgent}`}>
        <div className="activity-left">
          <span className={`live-radar-dot ${live ? "pulse" : "idle"}`} />
          <span className="agent-tag">
            <strong>{currentAgent.toUpperCase()}</strong>: {simState.pageTitle}
          </span>
        </div>
        <div className="activity-right">
          <span className="action-pill">{simState.actionText}</span>
        </div>
      </div>

      {/* Main Viewport Content Screen */}
      <div className="viewport-screen">
        {viewMode === "iframe" ? (
          <div className="iframe-container">
            <iframe
              src={simState.url}
              title="Live Target Website"
              className="live-iframe"
              sandbox="allow-scripts allow-forms allow-same-origin"
            />
            <div className="iframe-notice">
              <span>Note: Sites with strict <code>X-Frame-Options</code> may block framing.</span>
              <a href={simState.url} target="_blank" rel="noreferrer" className="btn-link">
                Open in new tab ↗
              </a>
            </div>
          </div>
        ) : (
          /* Agent View: Visual target webpage representation with interactive AI cursor */
          <div className="agent-canvas-stage">
            {/* Virtual Website Stage Mockup */}
            <div className="simulated-website">
              <nav className="sim-navbar">
                <div className="sim-logo">QA Target Web App</div>
                <div className="sim-nav-links">
                  <span className={`sim-link ${simState.pageRoute === "home" ? "active" : ""}`}>Home</span>
                  <span className={`sim-link ${simState.pageRoute === "login" ? "active" : ""}`}>Login</span>
                  <span className={`sim-link ${simState.pageRoute === "dashboard" ? "active" : ""}`}>Dashboard</span>
                </div>
              </nav>

              <div className="sim-content">
                {simState.pageRoute === "home" && (
                  <div className="sim-hero">
                    <h2>Welcome to the Sample Application</h2>
                    <p>This is the initial landing page being mapped by the autonomous Explorer agent.</p>
                    <div className={`sim-callout ${simState.activeSelector === "a[href='/login']" ? "highlight-target" : ""}`}>
                      <span className="sim-btn">Go to Login Page →</span>
                    </div>
                  </div>
                )}

                {simState.pageRoute === "login" && (
                  <div className="sim-login-card">
                    <h3>Account Sign In</h3>
                    <p className="muted small">Please enter your credentials to proceed.</p>

                    <div className={`sim-field ${simState.activeSelector === "#email" ? "highlight-target" : ""}`}>
                      <label htmlFor="sim-email">Email Address <span className="req">*</span></label>
                      <input
                        id="sim-email"
                        type="text"
                        readOnly
                        value={simState.fieldEmailValue}
                        placeholder="user@example.com"
                        className="sim-input"
                      />
                      {simState.activeSelector === "#email" && (
                        <span className="selector-tag">#email [active target]</span>
                      )}
                    </div>

                    <div className={`sim-field ${simState.activeSelector === "#password" ? "highlight-target" : ""}`}>
                      <label htmlFor="sim-password">Password <span className="req">*</span></label>
                      <input
                        id="sim-password"
                        type="password"
                        readOnly
                        value={simState.fieldPasswordValue}
                        placeholder="(left blank by tester)"
                        className="sim-input"
                      />
                    </div>

                    <div className={`sim-field ${simState.activeSelector === "button[type='submit']" ? "highlight-target" : ""}`}>
                      <button type="button" className="sim-submit-btn">
                        Sign In
                      </button>
                      {simState.activeSelector === "button[type='submit']" && (
                        <span className="selector-tag">button[type=&apos;submit&apos;]</span>
                      )}
                    </div>
                  </div>
                )}

                {simState.pageRoute === "dashboard" && (
                  <div className="sim-dashboard">
                    <div className="sim-bug-alert" role="alert">
                      <div className="alert-icon">⚠️</div>
                      <div>
                        <strong>BUG DETECTED: Missing Form Validation</strong>
                        <p>User bypassed password validation and entered the private dashboard!</p>
                      </div>
                    </div>

                    <div className="sim-welcome-box">
                      <h3>User Dashboard</h3>
                      <p className="muted">Logged in as: <code>user@example.com</code></p>
                      <div className="sim-card-grid">
                        <div className="sim-tile"><strong>Profile</strong><p>Status: Active</p></div>
                        <div className="sim-tile"><strong>Session</strong><p>Token: Valid</p></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Simulated AI Virtual Cursor Overlay */}
            {simState.cursorVisible && simState.cursorPos && (
              <div
                className="ai-virtual-cursor"
                style={{
                  left: `${simState.cursorPos.x}%`,
                  top: `${simState.cursorPos.y}%`,
                }}
              >
                <svg className="cursor-arrow" viewBox="0 0 24 24" width="22" height="22">
                  <path
                    fill="currentColor"
                    stroke="#ffffff"
                    strokeWidth="1.5"
                    d="M3 3l7 18 3-7 7-3L3 3z"
                  />
                </svg>
                <span className="cursor-agent-label">
                  {currentAgent}
                </span>
                <span className="cursor-pulse-wave" />
              </div>
            )}

            {/* If a real screenshot or test evidence exists, show a quick snapshot preview thumbnail toggle */}
            {latestScreenshot && (
              <div className="evidence-overlay-dock">
                <span className="dock-label">Latest Evidence Capture:</span>
                <a
                  href={latestScreenshot}
                  target="_blank"
                  rel="noreferrer"
                  className="dock-thumb-link"
                  title="Click to view full resolution evidence"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={latestScreenshot} alt="Latest test failure capture" />
                  <span className="zoom-hint">🔍 Expand</span>
                </a>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Viewport Footer Bar */}
      <div className="viewport-footer">
        <div className="viewport-footer-stat">
          <span className="muted small">Target:</span>
          <strong>{run.target_url}</strong>
        </div>
        <div className="viewport-footer-stat">
          <span className="muted small">Events Processed:</span>
          <strong>{events.length}</strong>
        </div>
        <div className="viewport-footer-stat">
          <span className="muted small">Active Selector:</span>
          <code>{simState.activeSelector ?? "none"}</code>
        </div>
      </div>
    </div>
  );
}
