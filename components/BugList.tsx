"use client";
import { useState } from "react";
import type { BugReport, Severity } from "@/lib/types";
import BugCard from "./BugCard";

const ORDER: Severity[] = ["critical", "high", "medium", "low"];

export default function BugList({ bugs }: { bugs: BugReport[] }) {
  const [filter, setFilter] = useState<Severity | "all">("all");
  if (bugs.length === 0) return <p className="empty">No bugs reported yet. They appear here as the Reporter files them.</p>;
  const shown = bugs
    .filter((b) => filter === "all" || b.severity === filter)
    .sort((a, b) => ORDER.indexOf(a.severity) - ORDER.indexOf(b.severity));
  return (
    <div className="stack">
      <div className="row gap" role="group" aria-label="Filter by severity">
        {(["all", ...ORDER] as const).map((s) => (
          <button key={s} className={`chip ${filter === s ? "on" : ""}`} onClick={() => setFilter(s)}>{s}</button>
        ))}
      </div>
      {shown.map((b) => <BugCard key={b.id} bug={b} />)}
      {shown.length === 0 && <p className="empty">No {filter} bugs.</p>}
    </div>
  );
}
