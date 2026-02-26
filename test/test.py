import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from test_cases import TEST_CASES

BASE_URL = os.getenv("SCHEDULER_BASE_URL", "http://localhost:5000")
URL = f"{BASE_URL.rstrip('/')}/schedule"
MAX_WORKERS = int(os.getenv("TEST_WORKERS", "8"))

def run_case(tc):
    payload = {
        "command": tc["command"],
        "history": tc.get("history")
    }
    expected_statuses = tc.get("expected_statuses", [])

    try:
        r = requests.post(URL, json=payload, timeout=30)
        output = r.json()
        status_code = r.status_code
    except Exception as e:
        output = {"detail": str(e)}
        status_code = None

    actual_status = output.get("status") if isinstance(output, dict) else None
    passed = True
    if expected_statuses:
        passed = actual_status in expected_statuses

    return {
        "name": tc["name"],
        "input": payload,
        "http_status": status_code,
        "expected_statuses": expected_statuses,
        "actual_status": actual_status,
        "passed": passed,
        "output": output,
    }

results = []
with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(TEST_CASES))) as executor:
    futures = [executor.submit(run_case, tc) for tc in TEST_CASES]
    for future in as_completed(futures):
        results.append(future.result())

results.sort(key=lambda x: x["name"])

with open("scheduler_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

passed_count = sum(1 for r in results if r["passed"])
print("Completed", len(results), "tests")
print("Passed:", passed_count)
print("Failed:", len(results) - passed_count)
print("API URL:", URL)
