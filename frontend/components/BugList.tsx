"use client";
import { useState } from "react";
import type { BugReport, Journey } from "@/lib/types";
import BugCard from "./BugCard";

interface BugListProps {
  bugs: BugReport[];
  journeys?: Journey[];
}

export default function BugList({ bugs, journeys = [] }: BugListProps) {
  const [activeTab, setActiveTab] = useState<"bugs" | "jr">("bugs");

  return (
    <section className="card">
      <div className="hd">
        <div className="tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "bugs"}
            onClick={() => setActiveTab("bugs")}
          >
            Bugs
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === "jr"}
            onClick={() => setActiveTab("jr")}
          >
            Journeys
          </button>
        </div>
        <small id="cnt">
          {activeTab === "bugs" ? `${bugs.length} found` : `${journeys.length} mapped`}
        </small>
      </div>

      {activeTab === "bugs" ? (
        <div className="list" id="bugs">
          {bugs.length === 0 ? (
            <p className="foot">No bugs reported yet.</p>
          ) : (
            bugs.map((b, i) => <BugCard key={b.id} bug={b} defaultOpen={i === 0} />)
          )}
        </div>
      ) : (
        <div className="list" id="jr">
          {journeys.length === 0 ? (
            <p className="foot">No journeys mapped yet.</p>
          ) : (
            journeys.map((j) => (
              <div key={j.id} className="jr">
                <b>{j.name}</b>
                <span>{j.pages.length} pages mapped</span>
              </div>
            ))
          )}
        </div>
      )}
    </section>
  );
}
