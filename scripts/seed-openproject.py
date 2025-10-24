#!/usr/bin/env python3
"""Seed an OpenProject instance with synthetic data for bench runs.

Two modes:

  python seed-openproject.py                   # 100 projects + 10k WPs via REST
  python seed-openproject.py --emit-webhooks N # bypass OP, produce N raw events to MSK

Env vars (read from ~/.config/openproject-mcp/.env.local or os.environ):
  OPENPROJECT_URL          base URL (default https://openproject.t3ja.com)
  OPENPROJECT_API_KEY      basic-auth user 'apikey' password
  KAFKA_BOOTSTRAP          for --emit-webhooks mode
  KAFKA_TOPIC              default 'openproject.events.raw'
  SEED_PROJECTS            project count (default 100)
  SEED_WORK_PACKAGES       WP count (default 10000)

Idempotent: skips projects/WPs whose identifier already exists.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import uuid
from base64 import b64encode
from pathlib import Path

import httpx

# ---- config ------------------------------------------------------------

ENV_FILE = Path.home() / ".config" / "openproject-mcp" / ".env.local"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

OP_URL = os.environ.get("OPENPROJECT_URL", "https://openproject.t3ja.com").rstrip("/")
OP_KEY = os.environ.get("OPENPROJECT_API_KEY", "")
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "openproject.events.raw")
N_PROJECTS = int(os.environ.get("SEED_PROJECTS", "100"))
N_WPS = int(os.environ.get("SEED_WORK_PACKAGES", "10000"))

STATUSES = [1, 7, 11, 12, 13, 14]  # OP default ids: New/InProgress/Closed/...
TYPES = [1, 2, 3, 4, 5, 6]
PRIORITIES = [7, 8, 9, 10]

# weighted distribution: most are New, fewer Closed
STATUS_WEIGHTS = [40, 30, 10, 10, 5, 5]
TYPE_WEIGHTS = [30, 25, 20, 10, 10, 5]
PRIORITY_WEIGHTS = [40, 35, 20, 5]


# ---- helpers -----------------------------------------------------------


def auth_header() -> dict[str, str]:
    if not OP_KEY:
        sys.exit(
            "OPENPROJECT_API_KEY not set - put it in ~/.config/openproject-mcp/.env.local"
        )
    token = b64encode(f"apikey:{OP_KEY}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def slug(prefix: str, idx: int) -> str:
    return f"{prefix}-{idx:04d}"


# ---- REST seed path ----------------------------------------------------


def existing_project_identifiers(client: httpx.Client) -> set[str]:
    """Page through projects, return set of identifiers for skip-on-conflict."""
    out: set[str] = set()
    offset = 0
    while True:
        r = client.get(
            f"{OP_URL}/api/v3/projects",
            params={"pageSize": 100, "offset": offset},
        )
        r.raise_for_status()
        body = r.json()
        for p in body.get("_embedded", {}).get("elements", []):
            out.add(p["identifier"])
        if offset + 100 >= body.get("total", 0):
            break
        offset += 100
    return out


def create_project(client: httpx.Client, idx: int) -> int | None:
    ident = slug("bench", idx)
    payload = {
        "name": f"Bench Project {idx}",
        "identifier": ident,
        "description": {
            "raw": (
                f"Synthetic project #{idx} created by seed-openproject.py "
                "for load tests."
            )
        },
        "public": False,
    }
    r = client.post(f"{OP_URL}/api/v3/projects", json=payload)
    if r.status_code == 422:
        # likely duplicate identifier - idempotent re-run
        return None
    if r.status_code not in (200, 201):
        print(f"  project {ident} failed: {r.status_code} {r.text[:200]}")
        return None
    return r.json()["id"]


def create_work_package(
    client: httpx.Client, project_id: int, idx: int
) -> bool:
    payload = {
        "subject": f"Synthetic WP {idx}",
        "description": {
            "raw": (
                f"WP #{idx} for load testing. status / type / priority are "
                "weighted-random to look realistic."
            )
        },
        "_links": {
            "type": {"href": f"/api/v3/types/{random.choices(TYPES, TYPE_WEIGHTS)[0]}"},
            "status": {
                "href": f"/api/v3/statuses/{random.choices(STATUSES, STATUS_WEIGHTS)[0]}"
            },
            "priority": {
                "href": (
                    f"/api/v3/priorities/{random.choices(PRIORITIES, PRIORITY_WEIGHTS)[0]}"
                )
            },
        },
    }
    r = client.post(
        f"{OP_URL}/api/v3/projects/{project_id}/work_packages", json=payload
    )
    if r.status_code not in (200, 201):
        return False
    return True


def seed_rest() -> int:
    print(f"target OpenProject: {OP_URL}")
    print(f"target projects: {N_PROJECTS}, work packages: {N_WPS}")

    headers = auth_header()
    with httpx.Client(headers=headers, timeout=30.0) as client:
        # sanity
        r = client.get(f"{OP_URL}/api/v3/users/me")
        r.raise_for_status()
        print(f"authenticated as: {r.json().get('name', '?')}")

        existing = existing_project_identifiers(client)
        print(f"already-present projects: {len(existing)}")

        project_ids: list[int] = []
        created = 0
        for i in range(N_PROJECTS):
            if slug("bench", i) in existing:
                continue
            pid = create_project(client, i)
            if pid is not None:
                project_ids.append(pid)
                created += 1
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/{N_PROJECTS} projects ({created} created)")

        print(f"projects: {created} created, {len(existing)} pre-existing")

        # need at least one project id to attach WPs to
        if not project_ids and existing:
            # fetch ids for existing project identifiers we want to use
            r = client.get(
                f"{OP_URL}/api/v3/projects",
                params={"pageSize": 100},
            )
            project_ids = [
                p["id"]
                for p in r.json().get("_embedded", {}).get("elements", [])
                if p["identifier"].startswith("bench-")
            ]

        if not project_ids:
            print("no projects to attach WPs to, exiting")
            return 1

        wp_created = 0
        for i in range(N_WPS):
            pid = random.choice(project_ids)
            if create_work_package(client, pid, i):
                wp_created += 1
            if (i + 1) % 500 == 0:
                print(f"  {i + 1}/{N_WPS} work packages ({wp_created} created)")

        print(f"work packages: {wp_created} created")
    return 0


# ---- Kafka direct emit -------------------------------------------------


def emit_webhooks(n: int) -> int:
    """Produce N synthetic OpenProject webhook events directly to MSK.

    Bypasses the OP app + ingest route. Used to push the consumer + cache
    pipeline without OpenProject in the way.
    """
    try:
        from confluent_kafka import Producer  # type: ignore
    except ImportError:
        sys.exit(
            "confluent-kafka not installed - pip install 'confluent-kafka[avro]' "
            "or use the docker-compose load harness instead"
        )

    if not KAFKA_BOOTSTRAP:
        sys.exit("KAFKA_BOOTSTRAP env not set")

    conf = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "client.id": "seed-openproject",
        "acks": "all",
        "compression.type": "lz4",
        "linger.ms": 50,
    }
    # MSK IAM path. only added when KAFKA_BOOTSTRAP looks like a 9098 endpoint
    if ":9098" in KAFKA_BOOTSTRAP:
        conf.update(
            {
                "security.protocol": "SASL_SSL",
                "sasl.mechanism": "OAUTHBEARER",
                "sasl.oauthbearer.config": "principal=mcp-server-bench",
            }
        )
        print("MSK IAM auth path. install aws-msk-iam-sasl-signer separately")

    producer = Producer(conf)

    def make_event(idx: int) -> dict[str, object]:
        return {
            "id": str(uuid.uuid4()),
            "event": random.choice(
                [
                    "work_package:created",
                    "work_package:updated",
                    "project:created",
                    "time_entry:created",
                ]
            ),
            "occurred_at": int(time.time() * 1000),
            "payload": {
                "work_package_id": idx,
                "project_id": random.randint(1, N_PROJECTS),
                "user_id": random.randint(1, 50),
                "subject": f"Synthetic event #{idx}",
            },
        }

    print(f"emitting {n} events to {KAFKA_TOPIC} on {KAFKA_BOOTSTRAP}")
    t0 = time.time()
    for i in range(n):
        ev = make_event(i)
        producer.produce(
            KAFKA_TOPIC,
            key=ev["id"].encode(),
            value=json.dumps(ev).encode(),
        )
        if (i + 1) % 5000 == 0:
            producer.poll(0)
            print(f"  {i + 1}/{n} sent (rate {(i + 1) / (time.time() - t0):.0f}/s)")
    producer.flush(timeout=60)
    elapsed = time.time() - t0
    print(f"done: {n} events in {elapsed:.1f}s ({n / elapsed:.0f}/s)")
    return 0


# ---- entrypoint --------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--emit-webhooks",
        type=int,
        default=0,
        metavar="N",
        help="Skip REST seed; emit N synthetic webhook events to MSK instead.",
    )
    args = parser.parse_args()

    if args.emit_webhooks > 0:
        return emit_webhooks(args.emit_webhooks)
    return seed_rest()


if __name__ == "__main__":
    sys.exit(main())
