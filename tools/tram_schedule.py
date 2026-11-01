#!/usr/bin/env python3
"""Tram timetable for the display: TRAM d'Alacant GTFS -> one small JSON file per stop.

Usage:
    python3 tools/tram_schedule.py [gtfs.zip | gtfs_dir] [out_dir]

Defaults: downloads the latest feed from the Mobility Database (mdb-1039) and writes tram/<stop_id>.json.
Each file lists departures from that stop on trips that end in Alicante centre (Luceros, Mercado,
Porta del Mar), per GTFS service, plus the date -> service map:

    {"updated": 1793560000, "stop": "10", "name": "Costa Blanca", "first": 20261013, "last": 20261231,
     "services": [[[303, 3], [308, 1], ...], ...],   # [minutes after midnight (can be >= 1440), line]
     "days": [[20261013, 0], ...]}                   # [yyyymmdd, service index]
"""
import collections
import csv
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

FEED_URL = "https://files.mobilitydatabase.org/mdb-1039/latest.zip"
CENTRE_STOPS = {"2", "3", "101"}  # Luceros, Mercado, Porta del Mar


def reader(src):
    if os.path.isdir(src):
        return lambda name: open(os.path.join(src, name), encoding="utf-8-sig", newline="")
    data = open(src, "rb").read() if os.path.exists(src) else urllib.request.urlopen(src, timeout=60).read()
    z = zipfile.ZipFile(io.BytesIO(data))
    return lambda name: io.TextIOWrapper(z.open(name), encoding="utf-8-sig", newline="")


def rows(open_, name):
    with open_(name) as f:
        return list(csv.DictReader(f))


def hms_to_min(s):
    h, m, _ = (int(x) for x in s.strip().split(":"))
    return h * 60 + m


def main(src, out):
    open_ = reader(src)
    trips = {t["trip_id"]: t for t in rows(open_, "trips.txt")}
    routes = {r["route_id"]: r["route_short_name"] for r in rows(open_, "routes.txt")}
    names = {s["stop_id"]: s["stop_name"] for s in rows(open_, "stops.txt")}

    seq = collections.defaultdict(list)
    for r in rows(open_, "stop_times.txt"):
        seq[r["trip_id"]].append((int(r["stop_sequence"]), r["stop_id"].strip(), r["departure_time"]))

    # stop -> service -> {(minute, line)}
    deps = collections.defaultdict(lambda: collections.defaultdict(set))
    for tid, v in seq.items():
        v.sort()
        if v[-1][1] not in CENTRE_STOPS:
            continue
        t = trips[tid]
        try:
            line = int(routes[t["route_id"]])
        except ValueError:
            continue
        for _, stop, dep in v[:-1]:
            deps[stop][t["service_id"]].add((hms_to_min(dep), line))

    dates = collections.defaultdict(list)  # service -> dates
    for r in rows(open_, "calendar_dates.txt"):
        if r["exception_type"].strip() == "1":
            dates[r["service_id"].strip()].append(int(r["date"]))

    os.makedirs(out, exist_ok=True)
    now = int(time.time())
    written = 0
    for stop, per_svc in deps.items():
        services = sorted(s for s in per_svc if dates.get(s))
        if not services:
            continue
        idx = {s: i for i, s in enumerate(services)}
        days = sorted((d, idx[s]) for s in services for d in dates[s])
        doc = {
            "updated": now,
            "stop": stop,
            "name": names.get(stop, ""),
            "first": days[0][0],
            "last": days[-1][0],
            "services": [sorted(per_svc[s]) for s in services],
            "days": days,
        }
        path = os.path.join(out, f"{stop}.json")
        old = None
        if os.path.exists(path):
            old = json.load(open(path))
            old["updated"] = now
        if old != json.loads(json.dumps(doc)):
            with open(path, "w") as f:
                json.dump(doc, f, separators=(",", ":"))
            written += 1
    print(f"stops: {len(deps)}, files changed: {written}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else FEED_URL, sys.argv[2] if len(sys.argv) > 2 else "tram")
