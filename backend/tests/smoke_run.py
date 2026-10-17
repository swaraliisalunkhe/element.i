"""Smoke run: start a run over HTTP and check the result. Owner: Member A.

The server must already be running. From the backend/ folder:
    python tests/smoke_run.py --mode mock
    python tests/smoke_run.py --mode real --url http://localhost:5000
Exit code 0 = all checks passed, 1 = something failed.
"""

import argparse
import sys
import time

import httpx


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Backend address")
    parser.add_argument("--url", default="http://localhost:5000", help="Web app to test")
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait for the run")
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=30) as client:
        try:
            health = client.get("/health")
        except httpx.HTTPError as exc:
            return fail(f"Cannot reach the backend at {args.api}: {exc}")
        if health.status_code != 200:
            return fail(f"/health returned {health.status_code}")
        print(f"OK: backend is up ({args.api})")

        created = client.post(
            "/api/runs",
            json={"name": "Smoke run", "target_url": args.url, "agent_mode": args.mode},
        )
        if created.status_code != 201:
            return fail(f"POST /api/runs returned {created.status_code}: {created.text}")
        run_id = created.json()["id"]
        print(f"OK: run created: {run_id} (mode: {args.mode}, target: {args.url})")

        deadline = time.monotonic() + args.timeout
        last_status = ""
        while True:
            run = client.get(f"/api/runs/{run_id}").json()
            if run["status"] != last_status:
                last_status = run["status"]
                print(f"    status: {last_status}")
            if run["status"] in ("completed", "failed"):
                break
            if time.monotonic() > deadline:
                return fail(f"The run did not finish within {args.timeout} seconds.")
            time.sleep(1)

        if run["status"] != "completed":
            return fail(f"The run ended as '{run['status']}': {run.get('error_message')}")
        print(f"OK: run completed. Summary: {run['summary']}")

        bugs = client.get(f"/api/runs/{run_id}/bugs").json()
        if not bugs:
            return fail("The run completed but no bug was reported.")
        for bug in bugs:
            print(f"    [{bug['severity']}] {bug['title']} (generated_by: {bug['generated_by']})")
        print(f"OK: {len(bugs)} bug report(s)")

        evidence_urls = [e["url"] for bug in bugs for e in bug["evidence"]]
        if not evidence_urls:
            return fail("No bug has screenshot evidence.")
        image = client.get(evidence_urls[0])
        if image.status_code != 200 or not image.headers["content-type"].startswith("image/"):
            return fail(f"Screenshot {evidence_urls[0]} did not load (status {image.status_code}).")
        print(f"OK: screenshot loads ({len(image.content)} bytes): {args.api}{evidence_urls[0]}")

        if all(bug["generated_by"] == "mock" for bug in bugs):
            print("NOTE: every bug is a MOCK FIXTURE. This proves the plumbing, not AI detection.")
        else:
            print("OK: at least one bug was produced by real agents (rule_based or llm).")

    print("SMOKE RUN PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())