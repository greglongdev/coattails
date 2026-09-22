"""CUSIP -> ticker via OpenFIGI, with a committed cache so lookups happen once.

13F filings identify securities by CUSIP only. OpenFIGI's mapping API is free
without a key at a modest rate (small batches, a few requests a minute), which
is plenty because the cache means only never-seen CUSIPs are looked up.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

URL = "https://api.openfigi.com/v3/mapping"
BATCH = 10          # keyless limit per request
PAUSE = 2.6         # keyless limit is ~25 requests/minute


def load_cache(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")


def map_cusips(cusips: list[str], cache: dict, session: requests.Session | None = None) -> dict:
    """Fill `cache` with {cusip: {"ticker":..., "name":..., "type":...} | None}."""
    session = session or requests.Session()
    todo = [c for c in dict.fromkeys(cusips) if c not in cache]
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        jobs = [{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in chunk]
        r = session.post(URL, json=jobs, headers={"Content-Type": "application/json"}, timeout=60)
        if r.status_code == 429:
            time.sleep(30)
            r = session.post(URL, json=jobs, headers={"Content-Type": "application/json"}, timeout=60)
        r.raise_for_status()
        for c, res in zip(chunk, r.json()):
            data = res.get("data") or []
            if data:
                d = data[0]
                cache[c] = {"ticker": d.get("ticker"), "name": d.get("name"), "type": d.get("securityType")}
            else:
                # Not on a US exchange (foreign line, private, bond). Try without exchange filter.
                cache[c] = None
        if i + BATCH < len(todo):
            time.sleep(PAUSE)
    # Second pass for the misses: identifiers starting with a letter are CINS
    # (foreign-domiciled issuers such as Chubb or ASML), which OpenFIGI maps only
    # under ID_CINS. Still US exchange, so the ticker is the one a US broker uses.
    misses = [c for c in todo if cache.get(c) is None and c[:1].isalpha()]
    for i in range(0, len(misses), BATCH):
        chunk = misses[i:i + BATCH]
        time.sleep(PAUSE)
        jobs = [{"idType": "ID_CINS", "idValue": c, "exchCode": "US"} for c in chunk]
        r = session.post(URL, json=jobs, headers={"Content-Type": "application/json"}, timeout=60)
        if r.status_code != 200:
            continue
        for c, res in zip(chunk, r.json()):
            data = res.get("data") or []
            if data:
                d = data[0]
                cache[c] = {"ticker": d.get("ticker"), "name": d.get("name"), "type": d.get("securityType")}
    return cache
