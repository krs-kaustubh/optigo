"""Record raw RailRadar station boards (plus response headers) as test fixtures.

Why this exists: RailRadar allows only 1,000 calls/month and 10/minute, so we
call it as little as possible, save the raw answer once, and run every test
offline against the saved files.

Each saved file holds the untouched JSON body, the HTTP status, the time we
asked, and the response headers (they show the rate-limit / quota numbers).
The API key is read from backend/.env and is never printed or saved.

Usage (from backend/):
    ../.venv/bin/python scripts/capture_boards.py PNVL VSH --hours 4
    ../.venv/bin/python scripts/capture_boards.py PNVL VSH --dry-run   # no calls

Codes captured in the same session share one snapshot folder, so Phase C can
pair trains across boards taken at (nearly) the same moment.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = BACKEND_DIR / "tests" / "fixtures" / "boards"
BASE_URL = "https://api.railradar.in/v1"

MAX_CODES_PER_RUN = 10        # one minute's worth of the 10/min limit
DEFAULT_PACE_SECONDS = 6.5    # 6.5 s apart = at most ~9 calls in any minute
VALID_HOURS = (2, 4, 6, 8)    # the only windows RailRadar accepts

# Headers worth showing on screen (all headers except secrets are still saved).
QUOTA_HEADER_PATTERN = re.compile(r"limit|remaining|reset|quota|retry|credit", re.I)
# Never write these to disk.
DROP_HEADERS = {"set-cookie", "authorization", "cookie"}


def quota_headers(headers: dict) -> dict:
    """The subset of response headers that describe rate limits / quota."""
    return {k: v for k, v in headers.items() if QUOTA_HEADER_PATTERN.search(k)}


def save_safe_headers(headers: dict) -> dict:
    """Lower-cased copy of the headers without anything secret."""
    return {k.lower(): v for k, v in headers.items() if k.lower() not in DROP_HEADERS}


def build_record(code: str, hours: int, requested_at: str, status: int,
                 headers: dict, body) -> dict:
    return {
        "code": code,
        "hours": hours,
        "requested_at": requested_at,
        "status": status,
        "headers": save_safe_headers(headers),
        "body": body,
    }


def train_count(body) -> int | None:
    try:
        return len(body["data"]["trains"])
    except (KeyError, TypeError):
        return None


def update_manifest(snapshot_dir: Path, record: dict) -> None:
    path = snapshot_dir / "manifest.json"
    manifest = json.loads(path.read_text()) if path.exists() else {"captures": []}
    manifest["captures"] = [c for c in manifest["captures"] if c["code"] != record["code"]]
    manifest["captures"].append({
        "code": record["code"], "hours": record["hours"],
        "requested_at": record["requested_at"], "status": record["status"],
        "trains": train_count(record["body"]),
    })
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("codes", nargs="+", help="RailRadar station codes, e.g. PNVL VSH")
    ap.add_argument("--hours", type=int, default=4, choices=VALID_HOURS)
    ap.add_argument("--snapshot", help="folder name under --out (default: current time)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--pace", type=float, default=DEFAULT_PACE_SECONDS,
                    help=f"seconds between calls (minimum {DEFAULT_PACE_SECONDS})")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, make no calls")
    args = ap.parse_args(argv)

    if args.pace < DEFAULT_PACE_SECONDS:
        ap.error(f"--pace must be at least {DEFAULT_PACE_SECONDS} seconds")

    codes = [c.upper() for c in args.codes]
    if len(codes) > MAX_CODES_PER_RUN:
        print(f"Refusing {len(codes)} codes in one run (max {MAX_CODES_PER_RUN}, "
              "the per-minute limit). Split it into separate runs.")
        return 2

    snapshot = args.snapshot or datetime.now().strftime("%Y-%m-%dT%H-%M")
    snapshot_dir = args.out / snapshot
    print(f"snapshot: {snapshot_dir}")
    print(f"codes:    {' '.join(codes)}   hours={args.hours}   pace={args.pace}s")
    if args.dry_run:
        print(f"DRY RUN: would make {len(codes)} call(s). Nothing sent.")
        return 0

    load_dotenv(BACKEND_DIR / ".env")
    key = os.environ.get("RAILRADAR_API_KEY", "")
    if not key:
        print("RAILRADAR_API_KEY is not set in backend/.env")
        return 2

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for i, code in enumerate(codes):
        if i:
            time.sleep(args.pace)
        asked = datetime.now().astimezone().isoformat(timespec="seconds")
        try:
            resp = requests.get(
                f"{BASE_URL}/stations/{code}/live",
                params={"hours": args.hours},
                headers={"Authorization": f"Bearer {key}"},
                timeout=20,
            )
        except requests.RequestException as exc:
            print(f"{code}: network error {type(exc).__name__}; stopping.")
            return 1
        try:
            body = resp.json()
        except ValueError:
            body = {"_non_json_body": resp.text[:500]}

        record = build_record(code, args.hours, asked, resp.status_code,
                              dict(resp.headers), body)
        (snapshot_dir / f"{code}.json").write_text(json.dumps(record, indent=2) + "\n")
        update_manifest(snapshot_dir, record)

        n = train_count(body)
        print(f"{code}: HTTP {resp.status_code}, trains={n}, quota headers="
              f"{quota_headers(dict(resp.headers))}")
        if resp.status_code != 200:
            print("Non-200 response saved; stopping so we don't burn more quota.")
            return 1
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
