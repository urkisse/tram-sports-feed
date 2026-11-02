#!/usr/bin/env python3
"""Today's decisive tennis matches for the display: quarterfinals, semifinals and finals of the
tournaments listed in events.json, from ESPN's public (unofficial) scoreboard. Writes matches.json:

    {"updated": 1793560000, "matches": [
      {"sport": "tennis", "t": 1793600000, "state": "pre", "title": "Alcaraz-Sinner",
       "round": "QF", "tour": "Paris Masters"}]}

state: pre (not started), in (playing now), post (finished). title is at most 14 ASCII characters.
tour is the event title from events.json. Writes the file only when something other than "updated" changed.
Usage: python3 tools/matches.py [--rounds "Round of 16,Quarterfinal"]  (the option is for testing)
"""
import datetime as dt
import json
import sys
import time
import unicodedata
import urllib.request

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{}/scoreboard"
ROUNDS = {"Quarterfinal": "QF", "Quarterfinals": "QF", "Semifinal": "SF", "Semifinals": "SF", "Final": "F", "Finals": "F"}
MAX_TITLE = 14


def ascii_name(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def surname(c):
    name = ascii_name((c.get("athlete") or {}).get("displayName") or "")
    return name.split()[-1] if name else "TBD"


def title(a, b):
    t = f"{a}-{b}"
    if len(t) <= MAX_TITLE:
        return t
    room = (MAX_TITLE - 1) // 2
    # коротше прізвище лишаємо цілим, довше обрізаємо
    if len(a) <= room:
        return f"{a}-{b[:MAX_TITLE - 1 - len(a)]}"
    if len(b) <= room:
        return f"{a[:MAX_TITLE - 1 - len(b)]}-{b}"
    return f"{a[:room]}-{b[:MAX_TITLE - 1 - room]}"


def main():
    rounds = dict(ROUNDS)
    if "--rounds" in sys.argv:
        rounds.update({r: r[:3] for r in sys.argv[sys.argv.index("--rounds") + 1].split(",")})
    tours = [e["title"] for e in json.load(open("events.json"))["events"] if e["sport"] == "tennis"]
    out = {}
    for tour_code in ("atp", "wta"):
        req = urllib.request.Request(URL.format(tour_code), headers={"User-Agent": "tram-display"})
        data = json.load(urllib.request.urlopen(req, timeout=30))
        for ev in data.get("events", []):
            tour = next((t for t in tours if t.lower() in ev.get("name", "").lower()), None)
            if not tour:
                continue
            for g in ev.get("groupings", []):
                if "Singles" not in g.get("grouping", {}).get("displayName", ""):
                    continue
                for c in g.get("competitions", []):
                    rnd = rounds.get(c.get("round", {}).get("displayName", ""))
                    if not rnd:
                        continue
                    t = int(dt.datetime.fromisoformat(c["date"].replace("Z", "+00:00")).timestamp())
                    if abs(t - time.time()) > 36 * 3600:
                        continue
                    p = c.get("competitors", [])
                    a, b = (surname(p[0]), surname(p[1])) if len(p) == 2 else ("TBD", "TBD")
                    out[c.get("id", f"{t}{a}")] = {"sport": "tennis", "t": t, "state": c.get("status", {}).get("type", {}).get("state", "pre"),
                                                   "title": title(a, b), "round": rnd, "tour": tour}
    # у файлі до 12 матчів: завершені не мають витісняти ті, що попереду
    matches = sorted(out.values(), key=lambda m: (m["state"] == "post", m["t"]))[:12]
    matches.sort(key=lambda m: m["t"])
    try:
        old = json.load(open("matches.json")).get("matches")
    except (OSError, ValueError):
        old = None
    if old != matches:
        with open("matches.json", "w") as f:
            json.dump({"updated": int(time.time()), "matches": matches}, f, indent=1)
    print(f"tournaments {tours}, matches {len(matches)}, changed {old != matches}")
    for m in matches:
        print(" ", dt.datetime.fromtimestamp(m["t"]).strftime("%d.%m %H:%M"), m["state"], m["round"], m["title"], "|", m["tour"])


if __name__ == "__main__":
    main()
