"use client";
import { useEffect, useRef } from "react";

export default function Home() {
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

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

    const BUGS = [
      {
        s: "critical",
        t: "Dashboard opens without logging in",
        c: "security",
        st: ["Open /dashboard?email=a registered email", "Do not log in first"],
        e: "Visitor is redirected to the login page.",
        a: "The dashboard loads with the account’s data.",
      },
      {
        s: "critical",
        t: "Login accepts an empty password",
        c: "form_validation",
        st: ["Open /login", "Type user@example.com into Email", "Leave Password empty", "Click Sign in"],
        e: "Form is rejected with “Password is required”.",
        a: "Visitor lands on /dashboard with no message.",
      },
      {
        s: "critical",
        t: "Password reset confirms but changes nothing",
        c: "functional",
        st: ["Open /reset-password", "Request a reset for a registered email", "Log in with a new password"],
        e: "The new password works.",
        a: "Only a confirmation message appears; the password never changes.",
      },
      {
        s: "high",
        t: "Weak password accepted at sign-up",
        c: "form_validation",
        st: ["Open /signup", "Enter a one-character password and the same confirmation", "Click Sign Up"],
        e: "Sign-up is rejected as too weak.",
        a: "The account is created.",
      },
    ];

    const bugsEl = $("#bugs");
    if (bugsEl) {
      bugsEl.innerHTML = BUGS.map(
        (b, i) =>
          `<details class="bug ${b.s}"${i ? "" : " open"}><summary><span class="chip sev-${b.s}">${
            b.s
          }</span>${b.t}<span class="cat">${b.c}</span></summary><div class="bd"><div><h5>Steps to reproduce</h5><ol>${b.st
            .map((x) => `<li>${x}</li>`)
            .join("")}</ol></div><div class="diff"><div class="e"><b>+ Expected</b>${
            b.e
          }</div><div class="a"><b>− Actual</b>${b.a}</div></div><div><h5>Evidence</h5>${ev(
            css("--cr")
          )}</div></div></details>`
      ).join("");
    }

    const jrEl = $("#jr");
    if (jrEl) {
      jrEl.innerHTML = [
        ["Sign up", 2],
        ["Log in", 3],
        ["Reset password", 2],
        ["Contact us", 1],
        ["Open dashboard", 2],
      ]
        .map(
          (j) =>
            `<div class="jr"><b>${j[0]}</b><span>${j[1]} pages mapped</span></div>`
        )
        .join("");
    }

    $$(".tabs button").forEach(
      (b) =>
        (b.onclick = () => {
          $$(".tabs button").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
          const bTab = $("#bugs");
          const jTab = $("#jr");
          const cnt = $("#cnt");
          if (bTab) bTab.hidden = b.dataset.p !== "bugs";
          if (jTab) jTab.hidden = b.dataset.p !== "jr";
          if (cnt) cnt.textContent = b.dataset.p === "bugs" ? "4 found" : "14 mapped";
        })
    );

    const RUNS = [
      ["qa-sample-app.onrender.com", "p-c", "Completed", 4, "2m 30s"],
      ["shop.example.com/checkout", "p-t", "Testing", 1, "1m 12s"],
      ["app.example.io", "p-e", "Exploring", 0, "0m 34s"],
      ["staging.example.dev", "p-q", "Queued", "–", "–"],
    ];
    const rowsEl = $("#rows");
    if (rowsEl) {
      rowsEl.innerHTML = RUNS.map(
        (r) =>
          `<tr><td class="sel">${r[0]}</td><td><span class="pill ${r[1]}"><b></b>${r[2]}</span></td><td>${r[3]}</td><td>${r[4]}</td></tr>`
      ).join("");
    }

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

    const goBtn = $("#go");
    if (goBtn) {
      goBtn.onclick = () => {
        const urlInput = $("#url") as HTMLInputElement | null;
        const v = urlInput?.value.trim() || "";
        const e = $("#err");
        if (v && !/^https?:\/\/\S+\.\S+/.test(v)) {
          if (e) e.textContent = "Enter a full URL starting with http:// or https://";
          return;
        }
        if (e) e.textContent = "";
        const addr = $("#addr");
        if (addr) addr.textContent = (v || "https://qa-sample-app.onrender.com") + "/login";
        run();
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

    // Trigger initial run after brief delay
    const initialRunTimer = setTimeout(() => {
      run();
    }, 800);

    return () => {
      window.removeEventListener("resize", size);
      window.removeEventListener("resize", mark);
      window.removeEventListener("pointermove", onPointerMove);
      cancelAnimationFrame(animFrameId);
      clearTimeout(initialRunTimer);
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
              <option>qa-sample-app</option>
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
                Launch QA Swarm ⚡
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
                    <span id="addr">https://qa-sample-app.onrender.com/login</span>
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
                  <p>Journeys discovered</p>
                  <strong>
                    <span data-n="14">14</span>
                  </strong>
                  <small>Mapped paths</small>
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
                  <p>Autonomous tests executed</p>
                  <strong>
                    <span data-n="48">48</span>
                  </strong>
                  <small>Total · 96% pass rate</small>
                  <div className="bar">
                    <i />
                  </div>
                </div>
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>Bugs caught</p>
                  <strong>
                    <span data-n="4">4</span>
                  </strong>
                  <div className="chips">
                    <span className="chip sev-critical">3 critical</span>
                    <span className="chip sev-high">1 high</span>
                  </div>
                </div>
                <div className="card kpi" style={{ "--k": "var(--glow)" } as React.CSSProperties}>
                  <p>Agent confidence score</p>
                  <strong>
                    <span data-n="98.4" data-d="1">
                      98.4
                    </span>
                    %
                  </strong>
                  <small>AI accuracy</small>
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
                      strokeDasharray="111 113"
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
                  <small id="cnt">4 found</small>
                </div>
                <div className="list" id="bugs" />
                <div className="list" id="jr" hidden />
              </section>
            </div>
          </div>

          <section className="card runs">
            <div className="hd">
              Recent runs <small>Sample data</small>
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

          <p className="foot">Design preview with sample data. Nothing here is a real test result.</p>
        </div>
      </div>
    </>
  );
}
