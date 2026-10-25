import type { RunStatus } from "@/lib/types";

const LABEL: Record<RunStatus, string> = {
  pending: "Queued", exploring: "Exploring", testing: "Testing",
  reporting: "Reporting", completed: "Completed", failed: "Failed",
};

export default function RunStatusBadge({ status }: { status: RunStatus }) {
  return <span className={`badge status-${status}`}>{LABEL[status]}</span>;
}
