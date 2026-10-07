"""Demo: submit a bulk job, poll until done, list results, download the ZIP.

Usage: python scripts/demo.py [base_url]
"""
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

payload = {
    "title": "Python Bootcamp 2026",
    "issuer_name": "Acme Academy",
    "issue_date": "2026-10-01",
    "recipients": [
        {"name": "Asha Rao", "email": "asha@example.com", "extra": "Distinction"},
        {"name": "Zoë Müller", "email": "zoe@example.com"},
        {"name": "A" * 90, "email": "longname@example.com"},
        {"name": "", "email": "bad-email"},
        {"name": "Asha Again", "email": "ASHA@example.com"},
    ],
}

with httpx.Client(base_url=BASE, timeout=30) as c:
    r = c.post("/api/jobs/", json=payload)
    r.raise_for_status()
    job_id = r.json()["id"]
    print(f"Job created: {job_id} (HTTP {r.status_code})\n")

    while True:
        s = c.get(f"/api/jobs/{job_id}/").json()
        print(f"{s['status']:<22} {s['progress_percent']:>5}%  "
              f"ok={s['success_count']} failed={s['failed_count']}")
        if s["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}:
            break
        time.sleep(0.5)

    print("\nPer-recipient results:")
    for item in c.get(f"/api/jobs/{job_id}/certificates/").json()["items"]:
        print(f"  #{item['index']} {item['name'][:20]:<20} {item['status']:<8} {item['error'] or ''}")

    z = c.get(f"/api/jobs/{job_id}/download/")
    z.raise_for_status()
    with open("demo_output.zip", "wb") as f:
        f.write(z.content)
    print("\nSaved demo_output.zip")
