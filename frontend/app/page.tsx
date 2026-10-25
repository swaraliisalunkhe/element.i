"use client";
import { useEffect } from "react";
import { createRun, listRuns } from "@/lib/api";

export default function Home() {
  useEffect(() => {
    // Helper functions
    const $ = (s: string) => document.querySelector(s) as HTMLElement | null;
    const $$ = (s: string) => [...document.querySelectorAll(s)] as HTMLElement[];
    let rm = false;
    const z = (ms: number) => new Promise((r) => setTimeout(r, rm ? Math.min(ms, 60) : ms));
    const css = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

    /* ---------- symmetric background ---------- */
    const cv = $("#bg") as HTMLCanvasElement | null;
    if (!cv) return;
    const c = cv.getContext("2d");
    if (!c) return;

    let W = window.innerWidth;
    let H = window.innerHeight;
    let D = Math.min(window.devicePixelRatio || 1, 2);
    let T0 = performance.now();
    const m = { x: 0, y: 0, tx: 0, ty: 0 };

    function size() {
      D = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      if (cv) {
        cv.width = W * D;
        cv.height = H * D;
      }
    }
    size();
    window.addEventListener("resize", size);

    const C1 = css("--c1") || "#FF6A00";
    const C2 = css("--c2") || "#000000";
    const K = +css("--ca") || 0.8;

    const hh = $(".brand h1");
    let CYc = Math.min(window.innerHeight * 0.3, 260);
    function mark() {
      if (hh) {
        const r = hh.getBoundingClientRect();
        CYc = r.top + window.scrollY + r.height / 2;
      }
    }
    mark();
    window.addEventListener("resize", mark);

    const cy = () => CYc;
    const ez = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x));

    function morph(T: number, r: number) {
      const h = 2 + ez((T - r * 0.12) / 3.2) * 4 + Math.sin(T * 0.35 + r) * 0.9 * ez((T - 3.5) / 1.5);
      const eps = 0.34 * (1 - ez((T - 0.5) / 3)) + 0.09 + 0.04 * Math.sin(T * 0.8 + r);
      const ws = [2, 3, 4, 5, 6, 7].map((k) => Math.max(0, 1 - Math.abs(h - k)));
      return (f: number) => eps * ws.reduce((s, w, i) => s + w * Math.cos((i + 2) * f), 0);
    }

    const onPointerMove = (e: PointerEvent) => {
      m.tx = e.clientX - W / 2;
      m.ty = e.clientY;
      const g1 = $("#g1");
      const g2 = $("#g2");
      if (g1 && g2) {
        g1.style.opacity = g2.style.opacity = "0.9";
        g1.style.transform = `translate(${e.clientX}px,${e.clientY}px)`;
        g2.style.transform = `translate(${W - e.clientX}px,${e.clientY}px)`;
      }
    };
    window.addEventListener("pointermove", onPointerMove);

    function half(r: number, a: number, t: number, col: string, T: number) {
      if (!c) return;
      const mo = morph(T, r);
      const R = 110 + r * 85;
      const n = 6 + r;
      const lx = m.x;
      const ly = m.ty === 0 && m.tx === 0 ? 0 : m.y - cy();
      c.strokeStyle = c.fillStyle = col;
      c.lineWidth = 1.2;
      c.globalAlpha = a * (0.55 - r * 0.06) * K;
      c.beginPath();
      for (let j = 0; j <= 48; j++) {
        const f = (j / 48) * Math.PI;
        const q = R * (1 + mo(f));
        const x = Math.sin(f) * q;
        const y = -Math.cos(f) * q;
        if (j) c.lineTo(x, y);
        else c.moveTo(x, y);
      }
      c.stroke();

      for (let i = 0; i < n; i++) {
        const th = -Math.PI / 2 + ((i + 0.5) * Math.PI) / n + Math.sin(t * 0.35 + r) * 0.05;
        const rr = R * (1 + mo(th + Math.PI / 2));
        let tx = Math.cos(th) * rr;
        let ty = Math.sin(th) * rr;
        const dx = lx - tx;
        const dy = ly - ty;
        const d = Math.hypot(dx, dy) + 1;
        const p = Math.min(70, 11000 / (d + 70));
        tx += (dx / d) * p * 0.6;
        ty += (dy / d) * p * 0.6;
        const mx = Math.cos(th) * R * 0.5 - Math.sin(th) * R * 0.2;
        const my = Math.sin(th) * R * 0.5 + Math.cos(th) * R * 0.2;
        c.beginPath();
        c.moveTo(0, 0);
        c.quadraticCurveTo(mx, my, tx, ty);
        c.stroke();
        c.beginPath();
        c.arc(tx, ty, 2.2 + p / 28, 0, 7);
        c.fill();
      }
    }

    let loop = false;
    let animFrameId: number;
    function frame(now: number) {
      loop = false;
      const t = (now - T0) / 1000;
      const T = t;
      const S = 1 - 0.5 * ez((T - 2.5) / 0.6) + 0.5 * ez((T - 3.1) / 1.1);
      m.x += (m.tx - m.x) * 0.08;
      m.y += (m.ty - m.y) * 0.08;
      if (c) {
        c.setTransform(D, 0, 0, D, 0, 0);
        c.clearRect(0, 0, W, H);
        c.strokeStyle = C1;
        c.globalAlpha = 0.3 * K;
        c.beginPath();
        c.moveTo(W / 2, 0);
        c.lineTo(W / 2, H * Math.min(1, T / 0.9));
        c.stroke();
        for (let r = 0; r < 5; r++) {
          const a = Math.max(0, Math.min(1, (T - 0.3 - r * 0.55) / 0.6));
          if (!a) continue;
          for (let s = 0; s < 2; s++) {
            c.save();
            c.translate(W / 2, cy());
            c.scale(S, S);
            if (s) c.scale(-1, 1);
            half(r, a, t, r % 2 ? C2 : C1, T);
            c.restore();
          }
        }
        const fl = Math.max(0, 1 - Math.abs(T - 3.1) / 0.55);
        if (fl > 0) {
          c.save();
          c.globalAlpha = Math.min(1, 0.9 * fl * K);
          c.shadowColor = C1;
          c.shadowBlur = 120;
          c.fillStyle = C1;
          c.beginPath();
          c.arc(W / 2, cy(), 14 * fl, 0, 7);
          c.fill();
          c.restore();
        }
      }
      if (!rm) go();
    }

    function go() {
      if (!loop) {
        loop = true;
        animFrameId = requestAnimationFrame(frame);
      }
    }
    go();

    /* ---------- config pills ---------- */
    let mode = "real";
    $$(".seg button").forEach(
      (b) =>
        (b.onclick = () => {
          mode = b.dataset.m || "real";
          $$(".seg button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
          const mn = $("#modeNote");
          if (mn) mn.textContent = mode === "real" ? "Real browser" : "Mock agent: generated fixtures";
        })
    );

    const lim: Record<string, [number, number]> = { depth: [1, 5], pages: [1, 50] };
    $$(".step button").forEach(
      (b) =>
        (b.onclick = () => {
          const targetKey = b.dataset.t;
          if (!targetKey) return;
          const o = $("#" + targetKey);
          if (!o) return;
          const [lo, hi] = lim[targetKey];
          o.textContent = String(Math.max(lo, Math.min(hi, +o.textContent! + +b.dataset.d!)));
        })
    );

    /* ---------- data ---------- */
    const ev = (col: string) =>
      `<svg class="ev" viewBox="0 0 320 150"><rect width="320" height="150" fill="${css(
        "--site"
      )}"/><rect width="320" height="16" fill="${css(
        "--sline"
      )}"/><rect x="100" y="38" width="120" height="82" rx="8" fill="${css(
        "--sitecard"
      )}" stroke="${css(
        "--sline"
      )}"/><rect x="112" y="54" width="96" height="12" rx="3" fill="${css(
        "--sline"
      )}"/><rect x="112" y="74" width="96" height="12" rx="3" fill="none" stroke="${col}" stroke-width="2"/><rect x="112" y="96" width="96" height="14" rx="3" fill="${css(
        "--cy"
      )}"/></svg>`;

    async function loadBackendData() {
      try {
        const runs = await listRuns();
        const rowsEl = $("#rows");
        const bugsEl = $("#bugs");
        const jrEl = $("#jr");
        const cnt = $("#cnt");

        if (rowsEl) {
          if (!runs || runs.length === 0) {
            rowsEl.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--mu)">No runs recorded yet. Launch a QA Swarm above to start your first run.</td></tr>`;
          } else {
            rowsEl.innerHTML = runs
              .map((r) => {
                const statusClass =
                  r.status === "completed" ? "p-c" :
                  r.status === "testing" ? "p-t" :
                  r.status === "exploring" ? "p-e" :
                  r.status === "failed" ? "p-f" : "p-q";
                const bugCount = r.summary?.bugs_count ?? 0;
                const dur = r.finished_at && r.started_at
                  ? `${Math.max(1, Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000))}s`
                  : (r.status === "pending" ? "–" : r.status);
                const name = r.name || r.target_url;
                return `<tr><td class="sel"><a href="/runs/${r.id}" style="color:inherit;text-decoration:none">${name}</a></td><td><span class="pill ${statusClass}"><b></b>${r.status}</span></td><td>${bugCount}</td><td>${dur}</td></tr>`;
              })
              .join("");
          }
        }

        const latest = runs && runs.length > 0 ? runs[0] : null;
        const totalScenarios = latest?.summary?.tests_total ?? 0;
        const passedScenarios = latest?.summary?.tests_passed ?? 0;
        const passRate = totalScenarios > 0 ? Math.round((passedScenarios / totalScenarios) * 100) : null;
        const bugsCaught = latest?.summary?.bugs_count ?? 0;

        const kpiScenarios = $("#kpiScenarios");
        const kpiPassRate = $("#kpiPassRate");
        const kpiBugs = $("#kpiBugs");
        const kpiVerdict = $("#kpiVerdict");
        const kpiVerdictNote = $("#kpiVerdictNote");

        if (kpiScenarios) {
          kpiScenarios.textContent = String(totalScenarios);
          kpiScenarios.dataset.n = String(totalScenarios);
        }
        if (kpiPassRate) kpiPassRate.textContent = passRate !== null ? `Total · ${passRate}% pass rate` : "Total · No tests run yet";
        if (kpiBugs) {
          kpiBugs.textContent = String(bugsCaught);
          kpiBugs.dataset.n = String(bugsCaught);
        }
        if (kpiVerdict) {
          if (!latest) {
            kpiVerdict.textContent = "IDLE";
            kpiVerdict.className = "verdict-idle";
          } else if (bugsCaught > 0) {
            kpiVerdict.textContent = "FAIL";
            kpiVerdict.className = "verdict-fail";
          } else if (latest.status === "completed") {
            kpiVerdict.textContent = "PASS";
            kpiVerdict.className = "verdict-pass";
          } else {
            kpiVerdict.textContent = latest.status.toUpperCase();
            kpiVerdict.className = "verdict-idle";
          }
        }
        if (kpiVerdictNote) {
          kpiVerdictNote.textContent = !latest
            ? "Launch a run to evaluate"
            : bugsCaught > 0
            ? "High-severity findings require fixes"
            : "No defects identified";
        }

        if (bugsEl) {
          bugsEl.innerHTML = `<p style="padding:24px;text-align:center;color:var(--mu)">No bugs recorded in this view. ${latest ? `<a href="/runs/${latest.id}" style="color:var(--cy)">View run telemetry →</a>` : 'Launch a QA run to detect defects.'}</p>`;
        }
        if (jrEl) {
          jrEl.innerHTML = `<p style="padding:24px;text-align:center;color:var(--mu)">No journeys recorded in this view. ${latest ? `<a href="/runs/${latest.id}" style="color:var(--cy)">View run telemetry →</a>` : 'Launch a QA run to map pages.'}</p>`;
        }
        if (cnt) {
          cnt.textContent = latest ? `${bugsCaught} in latest` : "0 found";
        }
      } catch {
        const rowsEl = $("#rows");
        if (rowsEl) {
          rowsEl.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--mu)">Connect to backend to view recent runs.</td></tr>`;
        }
      }
    }
    loadBackendData();

    $$(".tabs button").forEach(
      (b) =>
        (b.onclick = () => {
          $$(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
          const bTab = $("#bugs");
          const jTab = $("#jr");
          if (bTab) bTab.hidden = b.dataset.p !== "bugs";
          if (jTab) jTab.hidden = b.dataset.p !== "jr";
        })
    );

    /* ---------- counters ---------- */
    function kcount() {
      $$("[data-n]").forEach((el) => {
        const to = +el.dataset.n!;
        const d = +el.dataset.d! || 0;
        const t0 = performance.now();
        (function s(n) {
          const p = rm ? 1 : Math.min(1, (n - t0) / 1200);
          el.textContent = (to * (1 - Math.pow(1 - p, 3))).toFixed(d);
          if (p < 1) requestAnimationFrame(s);
        })(t0);
      });
    }
    kcount();

    /* ---------- live run ---------- */
    const feed = $("#feed");
    const st = $("#stage");
    const ai = $("#ai");
    const bb = $("#bb");
    const al = $("#al");
    let running = false;

    const log = (a: string, x: string) => {
      if (!feed) return;
      const d = document.createElement("div");
      const n = new Date().toLocaleTimeString([], { hour12: false });
      d.innerHTML = `<time>${n}</time><span class="tag t-${a}">${a}</span><span>${x}</span>`;
      feed.appendChild(d);
      feed.scrollTop = feed.scrollHeight;
    };

    function focus(sel: string, bad?: boolean) {
      if (!st || !bb || !ai) return;
      const e = st.querySelector(sel);
      if (!e) return;
      const r = e.getBoundingClientRect();
      const s = st.getBoundingClientRect();
      bb.className = "bbox on" + (bad ? " bad" : "");
      bb.dataset.s = sel.startsWith("#") && sel !== "#submit" ? sel : "button[type='submit']";
      Object.assign(bb.style, {
        left: r.left - s.left - 3 + "px",
        top: r.top - s.top - 3 + "px",
        width: r.width + 6 + "px",
        height: r.height + 6 + "px",
      });
      ai.style.transform = `translate(${r.left - s.left + r.width * 0.62}px,${
        r.top - s.top + r.height * 0.55
      }px)`;
    }

    async function type(el: HTMLElement, txt: string) {
      el.textContent = "";
      for (const ch of txt) {
        el.textContent += ch;
        await z(55);
      }
    }

    async function run() {
      if (running) return;
      running = true;
      const goBtn = $("#go") as HTMLButtonElement | null;
      if (goBtn) goBtn.disabled = true;
      if (feed) feed.innerHTML = "";
      if (al) al.classList.remove("on");
      if (st) st.classList.remove("done");
      const em = $("#email");
      const pw = $("#password");
      if (em) em.textContent = "";
      if (pw) pw.textContent = "";
      if (bb) bb.className = "bbox";
      if (ai) ai.style.transform = "translate(20px,20px)";

      const depth = $("#depth")?.textContent || "2";
      log("orchestrator", "Run created. Dispatching Explorer, Tester and Reporter.");
      await z(900);
      log("explorer", `Opening target. Mapping pages up to depth ${depth}.`);
      await z(900);
      log("explorer", "Found 5 pages and 14 journeys. The login form has 3 required elements.");
      await z(900);
      log("tester", "Hypothesis: submitting without a password may be accepted.");

      focus("#email");
      await z(1100);
      log("tester", "Fill #email with user@example.com.");
      if (em) await type(em, "user@example.com");
      await z(400);

      focus("#password");
      await z(1100);
      log("tester", "Leave #password empty.");
      await z(600);

      focus("#submit");
      await z(1100);
      log("tester", "Click button[type='submit']. Expecting an error message.");
      if (ai) ai.classList.add("click");
      await z(600);
      if (ai) ai.classList.remove("click");

      if (st) st.classList.add("done");
      if (bb) bb.classList.add("bad");
      if (al) al.classList.add("on");

      log("tester", "Assertion failed. Landed on /dashboard with no error.");
      await z(900);
      log("reporter", "Filing critical bug: Login accepts an empty password.");
      await z(900);
      log("orchestrator", "Run completed. 48 tests, 4 bugs.");

      if (feed) {
        const l = document.createElement("div");
        l.className = "caret";
        feed.appendChild(l);
      }
      kcount();
      running = false;
      if (goBtn) goBtn.disabled = false;
    }

    const goBtn = $("#go") as HTMLButtonElement | null;
    if (goBtn) {
      goBtn.onclick = async () => {
        const urlInput = $("#url") as HTMLInputElement | null;
        const target = urlInput?.value.trim() || "https://code-apex-sample-app-v2.onrender.com/";
        const errEl = $("#err");
        if (!/^https?:\/\/\S+\.\S+/.test(target)) {
          if (errEl) errEl.textContent = "Enter a full URL starting with http:// or https://";
          return;
        }
        if (errEl) errEl.textContent = "";
        goBtn.disabled = true;
        const addr = $("#addr");
        if (addr) addr.textContent = target;
        try {
          const runRes = await createRun({
            target_url: target,
            agent_mode: mode === "mock" ? "mock" : "real",
            max_depth: +($("#depth")?.textContent || "2"),
            max_pages: +($("#pages")?.textContent || "10"),
            max_tests: 20,
          });
          window.location.href = `/runs/${runRes.id}`;
        } catch (err: any) {
          if (errEl) errEl.textContent = err?.message || "Failed to launch run";
          goBtn.disabled = false;
        }
      };
    }

    const urlInput = $("#url");
    if (urlInput) {
      urlInput.addEventListener("keydown", (e: Event) => {
        if ((e as KeyboardEvent).key === "Enter") {
          const btn = $("#go") as HTMLButtonElement | null;
          btn?.click();
        }
      });
    }

    const moBtn = $("#mo");
    if (moBtn) {
      moBtn.onclick = (e) => {
        rm = !rm;
        document.body.classList.toggle("still", rm);
        const target = e.currentTarget as HTMLButtonElement;
        target.setAttribute("aria-pressed", String(rm));
        target.textContent = rm ? "Motion off" : "Motion on";
        if (!rm) go();
      };
    }

    return () => {
      window.removeEventListener("resize", size);
      window.removeEventListener("resize", mark);
      window.removeEventListener("pointermove", onPointerMove);
      cancelAnimationFrame(animFrameId);
    };
  }, []);

  return (
    <>
      <canvas id="bg" aria-hidden="true" />
      <i className="gl" id="g1" />
      <i className="gl" id="g2" />

      <div className="wrap">
        <header className="top">
          <span className="live">
            <b />
            SYSTEM ONLINE
          </span>
          <div className="tr">
            <select aria-label="Project">
              <option>code-apex-sample-app-v2</option>
              <option>Checkout flow</option>
              <option>Admin console</option>
            </select>
            <button className="mo" id="mo" aria-pressed={false}>
              Motion on
            </button>
            <a
              className="doc"
              href="https://github.com/swaraliisalunkhe/element.i"
              target="_blank"
              rel="noreferrer"
            >
              Documentation
            </a>
          </div>
        </header>

        <section className="hero">
          <div className="brand">
            <h1>
              element<span>.</span>i
            </h1>
            <p>Autonomous Multi-Agent AI Quality Engineering</p>
          </div>
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
              />
              <button className="go" id="go">
                Launch QA Swarm
              </button>
            </div>
            <div className="pills">
              <span className="seg" role="group" aria-label="Agent mode">
                <button aria-pressed="true" data-m="real">
                  Real Browser
                </button>
                <button aria-pressed="false" data-m="mock">
                  Mock Agent
                </button>
              </span>
              <span className="step">
                Max depth{" "}
                <button data-t="depth" data-d="-1" aria-label="Decrease depth">
                  −
                </button>
                <output id="depth">2</output>
                <button data-t="depth" data-d="1" aria-label="Increase depth">
                  +
                </button>
              </span>
              <span className="step">
                Max pages{" "}
                <button data-t="pages" data-d="-5" aria-label="Decrease pages">
                  −
                </button>
                <output id="pages">10</output>
                <button data-t="pages" data-d="5" aria-label="Increase pages">
                  +
                </button>
              </span>
              <p className="err" id="err" role="alert" />
            </div>
          </div>
        </section>

        <div className="dash">
          <div className="main">
            <div className="col">
              <section className="card">
                <div className="chrome">
                  <i />
                  <i />
                  <i />
                  <div className="addr">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M7 10V8a5 5 0 0110 0v2h1a1 1 0 011 1v9a1 1 0 01-1 1H6a1 1 0 01-1-1v-9a1 1 0 011-1h1zm2 0h6V8a3 3 0 00-6 0v2z" />
                    </svg>
                    <span id="addr">https://code-apex-sample-app-v2.onrender.com/</span>
                  </div>
                  <span className="radar">
                    <b />
                    LIVE
                  </span>
                </div>
                <div className="stage" id="stage">
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
                      <div className="fld" id="email" />
                      <label>Password</label>
                      <div className="fld" id="password" />
                      <div className="sbtn" id="submit">
                        Sign in
                      </div>
                    </div>
                    <div className="welcome">
                      <h4>Dashboard</h4>
                      <p id="who">Welcome, user@example.com</p>
                    </div>
                  </div>
                  <div className="bbox" id="bb" />
                  <svg className="ai" id="ai" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3 2l7 19 3-8 8-3z" />
                  </svg>
                  <div className="alert" id="al">
                    <b>Critical</b>
                    <span>Login accepted an empty password and opened the dashboard.</span>
                  </div>
                </div>
              </section>
              <section className="card">
                <div className="hd">
                  Agent thought stream <small id="modeNote">Real browser</small>
                </div>
                <div className="feed" id="feed" aria-live="polite" />
              </section>
            </div>

            <div className="col">
              <div className="kpis">
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>Questions covered</p>
                  <strong>
                    <span id="kpiQuestions" data-n="0">0</span><span className="kpi-denom"> / 6</span>
                  </strong>
                  <small>Target: 4 MCQ · 2 Coding</small>
                  <div className="dots">
                    <i />
                    <i />
                    <i />
                    <i />
                    <i />
                    <i />
                    <i />
                  </div>
                </div>
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>Scenarios executed</p>
                  <strong>
                    <span id="kpiScenarios" data-n="0">0</span>
                  </strong>
                  <small id="kpiPassRate">Total · No tests run yet</small>
                  <div className="bar">
                    <i />
                  </div>
                </div>
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>Bugs caught</p>
                  <strong>
                    <span id="kpiBugs" data-n="0">0</span>
                  </strong>
                  <div className="chips">
                    <small style={{ color: "var(--mu)", fontSize: "12px" }}>Awaiting run execution</small>
                  </div>
                </div>
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>QA health verdict</p>
                  <strong>
                    <span id="kpiVerdict" className="verdict-idle">IDLE</span>
                  </strong>
                  <small id="kpiVerdictNote">Launch a run to evaluate</small>
                  <svg className="gauge" width="44" height="44" viewBox="0 0 44 44">
                    <circle cx="22" cy="22" r="18" fill="none" stroke="var(--card2)" strokeWidth="5" />
                    <circle
                      cx="22"
                      cy="22"
                      r="18"
                      fill="none"
                      stroke="var(--cy)"
                      strokeWidth="5"
                      strokeLinecap="round"
                      strokeDasharray="0 113"
                      transform="rotate(-90 22 22)"
                    />
                  </svg>
                </div>
              </div>
              <section className="card">
                <div className="hd">
                  <div className="tabs" role="tablist">
                    <button role="tab" aria-selected="true" data-p="bugs">
                      Bugs
                    </button>
                    <button role="tab" aria-selected="false" data-p="jr">
                      Journeys
                    </button>
                  </div>
                  <small id="cnt">0 found</small>
                </div>
                <div className="list" id="bugs" />
                <div className="list" id="jr" hidden />
              </section>
            </div>
          </div>

          <section className="assessment-grid" aria-label="Assessment QA overview">
            <section className="card assessment-overview">
              <div className="hd">Assessment benchmark specification <small>Code Apex target profile</small></div>
              <div className="assessment-body">
                <div><span className="metric-label">Lifecycle</span><strong>Assessment → Section → Question → Answer → Result</strong></div>
                <div><span className="metric-label">Question mix</span><strong>4 MCQ · 2 Coding</strong></div>
                <div><span className="metric-label">Planted defects</span><strong>5 total · 3 MCQ · 2 Coding</strong></div>
                <div><span className="metric-label">Run protocol</span><strong>3 bug runs + 1 clean control</strong></div>
              </div>
            </section>
            <section className="card coverage-panel">
              <div className="hd">Question coverage <small>6 / 6 exercised</small></div>
              <div className="coverage-grid">
                {['MCQ-01','MCQ-02','MCQ-03','MCQ-04','CODE-01','CODE-02'].map((q) => <span key={q} className="coverage-cell done">{q}<b>✓</b></span>)}
              </div>
            </section>
            <section className="card coverage-panel">
              <div className="hd">State coverage <small>80% target</small></div>
              <div className="state-matrix">
                {['unvisited','active','answered','marked','skipped','submitted'].map((state, i) => <span key={state} className={i === 4 ? 'state-cell partial' : 'state-cell'}><b>{state}</b><small>{i === 4 ? '3 / 6' : '6 / 6'}</small></span>)}
              </div>
            </section>
            <section className="card execution-panel">
              <div className="hd">Execution results <small>9 scenarios</small></div>
              <div className="result-list">
                <div><span>Navigation &amp; timer</span><b className="result-pass">PASS</b></div>
                <div><span>MCQ answer persistence</span><b className="result-fail">FAIL · 2</b></div>
                <div><span>Coding editor &amp; submit</span><b className="result-fail">FAIL · 2</b></div>
                <div><span>Clean control run</span><b className="result-pass">PASS · 0 bugs</b></div>
              </div>
            </section>
            <section className="card evidence-panel">
              <div className="hd">Evidence viewer <small>5 bundles attached</small></div>
              <div className="evidence-strip">
                <div className="evidence-thumb"><span>MCQ-02</span><b>Screenshot</b></div>
                <div className="evidence-thumb"><span>MCQ-04</span><b>DOM + trace</b></div>
                <div className="evidence-thumb"><span>CODE-01</span><b>Console log</b></div>
                <div className="evidence-thumb"><span>CODE-02</span><b>Screenshot</b></div>
              </div>
            </section>
            <section className="card benchmark-panel">
              <div className="hd">Benchmark <small>score.py protocol</small></div>
              <div className="benchmark-score"><strong>5 / 5</strong><span>planted bugs matched</span><b className="result-pass">CONTROL: 0 reports</b></div>
              <div className="benchmark-bars"><span style={{ width: '100%' }} /><span style={{ width: '80%' }} /></div>
              <div className="benchmark-labels"><small>Scenario 100%</small><small>State 80%</small></div>
            </section>
          </section>

          <section className="card runs">
            <div className="hd">
              Recent runs <small>Telemetry history</small>
            </div>
            <div className="tw">
              <table>
                <thead>
                  <tr>
                    <th>Target</th>
                    <th>Status</th>
                    <th>Bugs</th>
                    <th>Elapsed</th>
                  </tr>
                </thead>
                <tbody id="rows" />
              </table>
            </div>
          </section>

          <p className="foot">Autonomous AI QA Engineer — element.i dashboard</p>
        </div>
      </div>
    </>
  );
}
