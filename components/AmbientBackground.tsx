"use client";
import { useEffect, useRef } from "react";

export default function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const g1Ref = useRef<HTMLElement>(null);
  const g2Ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let W = window.innerWidth;
    let H = window.innerHeight;
    let D = Math.min(window.devicePixelRatio || 1, 2);

    const size = () => {
      D = Math.min(window.devicePixelRatio || 1, 2);
      W = window.innerWidth;
      H = window.innerHeight;
      if (cv) {
        cv.width = W * D;
        cv.height = H * D;
      }
    };
    size();
    window.addEventListener("resize", size);

    const C1 = "#2563eb";
    const C2 = "#000000";
    const K = 0.8;
    const T0 = performance.now();
    const m = { x: 0, y: 0, tx: 0, ty: 0 };

    let CYc = Math.min(window.innerHeight * 0.3, 260);
    const updateCYc = () => {
      const hh = document.querySelector(".brand h1");
      if (hh) {
        const r = hh.getBoundingClientRect();
        CYc = r.top + window.scrollY + r.height / 2;
      }
    };
    updateCYc();
    window.addEventListener("resize", updateCYc);

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
      if (g1Ref.current && g2Ref.current) {
        g1Ref.current.style.opacity = "0.9";
        g2Ref.current.style.opacity = "0.9";
        g1Ref.current.style.transform = `translate(${e.clientX}px,${e.clientY}px)`;
        g2Ref.current.style.transform = `translate(${W - e.clientX}px,${e.clientY}px)`;
      }
    };
    window.addEventListener("pointermove", onPointerMove);

    function half(r: number, a: number, t: number, col: string, T: number) {
      if (!ctx) return;
      const mo = morph(T, r);
      const R = 110 + r * 85;
      const n = 6 + r;
      const lx = m.x;
      const ly = m.ty === 0 && m.tx === 0 ? 0 : m.y - cy();
      ctx.strokeStyle = ctx.fillStyle = col;
      ctx.lineWidth = 1.2;
      ctx.globalAlpha = a * (0.55 - r * 0.06) * K;
      ctx.beginPath();
      for (let j = 0; j <= 48; j++) {
        const f = (j / 48) * Math.PI;
        const q = R * (1 + mo(f));
        const x = Math.sin(f) * q;
        const y = -Math.cos(f) * q;
        if (j) ctx.lineTo(x, y);
        else ctx.moveTo(x, y);
      }
      ctx.stroke();

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
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.quadraticCurveTo(mx, my, tx, ty);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(tx, ty, 2.2 + p / 28, 0, 7);
        ctx.fill();
      }
    }

    function frame(now: number) {
      if (!ctx) return;
      const t = (now - T0) / 1000;
      const T = t;
      const S = 1 - 0.5 * ez((T - 2.5) / 0.6) + 0.5 * ez((T - 3.1) / 1.1);
      m.x += (m.tx - m.x) * 0.08;
      m.y += (m.ty - m.y) * 0.08;

      ctx.setTransform(D, 0, 0, D, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.strokeStyle = C1;
      ctx.globalAlpha = 0.3 * K;
      ctx.beginPath();
      ctx.moveTo(W / 2, 0);
      ctx.lineTo(W / 2, H * Math.min(1, T / 0.9));
      ctx.stroke();

      for (let r = 0; r < 5; r++) {
        const a = Math.max(0, Math.min(1, (T - 0.3 - r * 0.55) / 0.6));
        if (!a) continue;
        for (let s = 0; s < 2; s++) {
          ctx.save();
          ctx.translate(W / 2, cy());
          ctx.scale(S, S);
          if (s) ctx.scale(-1, 1);
          half(r, a, t, r % 2 ? C2 : C1, T);
          ctx.restore();
        }
      }

      const fl = Math.max(0, 1 - Math.abs(T - 3.1) / 0.55);
      if (fl > 0) {
        ctx.save();
        ctx.globalAlpha = Math.min(1, 0.9 * fl * K);
        ctx.shadowColor = C1;
        ctx.shadowBlur = 120;
        ctx.fillStyle = C1;
        ctx.beginPath();
        ctx.arc(W / 2, cy(), 14 * fl, 0, 7);
        ctx.fill();
        ctx.restore();
      }

      animId = requestAnimationFrame(frame);
    }

    animId = requestAnimationFrame(frame);

    // Initial triggers for intro classes on body
    const t1 = setTimeout(() => document.body.classList.add("b"), 300);
    const t2 = setTimeout(() => document.body.classList.add("c"), 800);
    const t3 = setTimeout(() => document.body.classList.add("d"), 1200);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", size);
      window.removeEventListener("resize", updateCYc);
      window.removeEventListener("pointermove", onPointerMove);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  return (
    <>
      <canvas id="bg" ref={canvasRef} aria-hidden="true" />
      <i className="gl" id="g1" ref={g1Ref} />
      <i className="gl" id="g2" ref={g2Ref} />
    </>
  );
}
