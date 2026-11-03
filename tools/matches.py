#!/usr/bin/env python3
"""Today's decisive matches for the display, written to matches.json:

    {"updated": 1793560000, "matches": [
      {"sport": "tennis", "t": 1793600000, "state": "pre", "title": "Alcaraz-Sinner",
       "round": "QF", "tour": "Paris Masters"}]}

state: pre (not started), in (playing now), post (finished). title is at most 14 ASCII characters.
tour is the event title from events.json. "tbc": true means the time is not known (shown without a time).
"matches" is for the banner: decisive rounds only. "games" is for the tournament page on the board: every round
of today and tomorrow (Europe/Madrid), same fields, "full" up to 30 characters with the world ranking after a tennis player's name when known.
Writes the file only when something other than "updated" changed.

Sources, each only for events listed in events.json and only near their dates:
- tennis: ESPN public scoreboard (unofficial), main draw singles.
- padel: FIP order of play at widget.matchscorerlive.com, event field "oop" (e.g. "FIP-2026-4516"),
  all rounds. Many matches only say "Followed by", those have no time.
- dota2, cs2: Liquipedia:Matches through the MediaWiki API (CC-BY-SA, at most one parse per 30 s),
  event field "lq" (part of the tournament name), the banner only uses playoff or final stages.

Usage: python3 tools/matches.py [--test-padel "Group stage"] [--test-lq "BLAST Rivals"]  (for testing)
"""
import datetime as dt
import gzip
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
import zoneinfo

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{}/scoreboard"
RANK_URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{}/rankings"
ROUNDS = {"Quarterfinal": "QF", "Quarterfinals": "QF", "Semifinal": "SF", "Semifinals": "SF", "Final": "F", "Finals": "F"}
BANNER_ROUNDS = ("QF", "SF", "F", "PO", "T")
MAX_TITLE = 14
MAX_GAME_TITLE = 30
MAX_GAMES_PER_TOUR, MAX_GAMES = 40, 80
MADRID = zoneinfo.ZoneInfo("Europe/Madrid")
OOP = "https://widget.matchscorerlive.com/screen/oopbyday/{}/{}?t=tol"
LQ = "https://liquipedia.net/{}/api.php?action=parse&page=Liquipedia:Matches&format=json&prop=text"
UA = "tram-display/1.0 (https://github.com/urkisse/tram-sports-feed)"


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


def game_title(a, b, ra=None, rb=None):
    """"Zverev 1 - Alcaraz 2": місце в рейтингу не обрізаємо, лише довше ім'я."""
    tail = lambda r: f" {r}" if r else ""
    while len(a) + len(tail(ra)) + len(b) + len(tail(rb)) + 3 > MAX_GAME_TITLE:
        if len(a) >= len(b):
            a = a[:-1]
        else:
            b = b[:-1]
    return f"{a}{tail(ra)} - {b}{tail(rb)}"


def tennis_round(name):
    if name.startswith("Qualifying"):
        return None
    m = re.fullmatch(r"Round (\d+)", name)
    return ROUNDS.get(name) or (f"R{m.group(1)}" if m else name[:3])


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return gzip.decompress(data).decode() if r.headers.get("Content-Encoding") == "gzip" else data.decode()


def near(e, days=1):
    """Подія йде зараз або ось-ось: не чіпаємо джерела дарма."""
    now = time.time()
    return e["t"] - days * 86400 <= now <= e.get("end", e["t"]) + days * 86400


def tennis_ranks():
    """Місця в рейтингах ATP і WTA (топ-150 кожного). Без них турнір усе одно показуємо."""
    ranks = {}
    for tour_code in ("atp", "wta"):
        try:
            for r in json.loads(fetch(RANK_URL.format(tour_code)))["rankings"][0]["ranks"]:
                ranks[r["athlete"]["displayName"]] = r["current"]
        except Exception as e:
            print(f"ranks {tour_code} failed: {e}")
    return ranks


def tennis(events):
    out = {}
    ranks = tennis_ranks()
    tours = [e["title"] for e in events if e["sport"] == "tennis"]
    for tour_code in ("atp", "wta"):
        data = json.loads(fetch(URL.format(tour_code)))
        for ev in data.get("events", []):
            tour = next((t for t in tours if t.lower() in ev.get("name", "").lower()), None)
            if not tour:
                continue
            for g in ev.get("groupings", []):
                if "Singles" not in g.get("grouping", {}).get("displayName", ""):
                    continue
                for c in g.get("competitions", []):
                    rnd = tennis_round(c.get("round", {}).get("displayName", ""))
                    if not rnd:
                        continue
                    t = int(dt.datetime.fromisoformat(c["date"].replace("Z", "+00:00")).timestamp())
                    if abs(t - time.time()) > 60 * 3600:
                        continue
                    p = c.get("competitors", [])
                    a, b = (surname(p[0]), surname(p[1])) if len(p) == 2 else ("TBD", "TBD")
                    ra, rb = (ranks.get((x.get("athlete") or {}).get("displayName")) for x in p) if len(p) == 2 else (None, None)
                    m = {"sport": "tennis", "t": t, "state": c.get("status", {}).get("type", {}).get("state", "pre"),
                         "title": title(a, b), "full": game_title(a, b, ra, rb), "round": rnd, "tour": tour}
                    if c.get("timeValid") is False:
                        m["tbc"] = True
                    out[c.get("id", f"{t}{a}")] = m
    return list(out.values())


def tokens(page):
    t = re.sub(r"(?s)<(script|style).*?</\1>", " ", page)
    return [x.strip() for x in html.unescape(re.sub(r"<[^>]+>", "\n", t)).split("\n") if x.strip()]


def padel_round(name, extra):
    n = name.lower()
    if extra and extra.lower() in n:
        return "T"
    return "QF" if "quarter" in n else "SF" if "semi" in n else "F" if "final" in n else "GS"


def padel(events, extra=None):
    out = []
    for e in events:
        if e["sport"] != "padel" or not (e.get("oop") or e.get("fip")) or not (near(e) or extra):
            continue
        # код розкладу з'являється на сторінці турніру незадовго до старту
        oop = e.get("oop")
        if not oop:
            found = re.findall(r"oopbyday/([A-Za-z]+-\d{4}-\d+)", fetch(e["fip"], {"User-Agent": "Mozilla/5.0"}))
            if not found:
                continue
            oop = found[0]
        first = fetch(OOP.format(oop, 1))
        tabs = re.findall(r'play-day-date">([A-Z]{3} \d+)<', first)
        for day, label in enumerate(tabs, 1):
            year = dt.datetime.fromtimestamp(e["t"]).year
            date = dt.datetime.strptime(f"{label} {year}", "%b %d %Y")
            if abs((date.date() - dt.date.today()).days) > 1 and not (extra and day == 1):
                continue
            tk = tokens(first if day == 1 else fetch(OOP.format(oop, day)))
            # часовий пояс турніру: сторінка показує місцевий час
            off = None
            for i, x in enumerate(tk):
                if x == "Local Time" and i + 1 < len(tk):
                    local = dt.datetime.strptime(tk[i + 1], "%m/%d/%Y %I:%M:%S %p")
                    off = round((local - dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)).total_seconds() / 1800) * 1800
                    break
            i, last = 0, None
            while i < len(tk):
                m = re.match(r"(Starting at|Not before) (\d+:\d+ [AP]M)", tk[i])
                if not (m or tk[i] == "Followed by"):
                    i += 1
                    continue
                when = None
                if m and off is not None:
                    clock = dt.datetime.strptime(m.group(2), "%I:%M %p")
                    when = int(date.replace(hour=clock.hour, minute=clock.minute, tzinfo=dt.timezone.utc).timestamp()) - off
                    last = when
                i += 1
                # заголовок корту: час іще раз, місцевий час, потім стать
                while i < len(tk) and (tk[i] in ("Men", "Women", "Local Time") or re.fullmatch(r"\d+/\d+/\d+ .*|Starting at .*|Not before .*", tk[i])):
                    i += 1
                if i >= len(tk):
                    break
                rnd = padel_round(tk[i], extra)
                i += 1
                names, block = [[], []], []
                side = 0
                while i < len(tk) and not re.match(r"(Starting at|Not before|Followed by)", tk[i]) and tk[i] not in ("Completed", "MATCH STATS"):
                    x = tk[i]
                    if re.fullmatch(r"\d+|-", x):
                        if names[0]:
                            side = 1
                    elif not re.fullmatch(r"[A-Z]\.?|.*:\d\d|\W+", x):
                        names[side].append(ascii_name(x).split()[-1] if ascii_name(x).split() else "")
                    block.append(x)
                    i += 1
                done = i < len(tk) and tk[i] == "Completed"
                played = any(re.fullmatch(r"\d+", x) for x in block)
                a, b = names[0][0] if names[0] else "TBD", names[1][0] if names[1] else "TBD"
                pair = lambda n: "/".join(n[:2]) or "TBD"
                m2 = {"sport": "padel", "t": when or last or int(date.replace(hour=12, tzinfo=dt.timezone.utc).timestamp()),
                      "state": "post" if done else "in" if played else "pre", "title": title(a, b),
                      "full": game_title(pair(names[0]), pair(names[1])), "round": rnd, "tour": e["title"]}
                if not when:
                    m2["tbc"] = True
                out.append(m2)
    return out


def esports(events, test=None):
    out = []
    wikis = (("cs2", "counterstrike"), ("dota2", "dota2"))
    for i, (sport, wiki) in enumerate(wikis):
        watch = {e["lq"]: e["title"] for e in events if e["sport"] == sport and e.get("lq") and near(e)}
        if test:
            watch[test] = test
        if not watch:
            continue
        if i and out is not None:
            time.sleep(31)  # умови Liquipedia: не частіше одного parse на 30 с
        page = json.loads(fetch(LQ.format(wiki)))["parse"]["text"]["*"]
        for block in page.split('class="match-info"')[1:]:
            ts = re.search(r'data-timestamp="(\d+)"', block)
            name = re.search(r'match-info-tournament-name".*?<span>(.*?)</span>', block, re.S)
            if not ts or not name:
                continue
            tour_name = html.unescape(name.group(1))
            tour = next((v for k, v in watch.items() if k.lower() in tour_name.lower()), None)
            if not tour:
                continue
            t = int(ts.group(1))
            if abs(t - time.time()) > 60 * 3600:
                continue
            teams = re.findall(r'match-info-header-opponent.*?title="([^"]+)"', block, re.S)
            short = [ascii_name(html.unescape(x)).replace("Team ", "").split(" (")[0].replace(" ", "") for x in teams[:2]]
            a, b = (short + ["TBD", "TBD"])[:2]
            finished = 'data-finished="finished"' in block
            # у списку "upcoming" лишаються давно зіграні матчі без позначки: понад 6 годин вважаємо завершеними
            now = time.time()
            state = "post" if finished or now - t > 6 * 3600 else "in" if t <= now else "pre"
            rnd = "PO" if test or re.search(r"(?i)playoff|final", tour_name) else "GS"
            out.append({"sport": sport, "t": t, "state": state, "title": title(a, b), "full": game_title(a, b), "round": rnd, "tour": tour})
    return out


def main():
    arg = lambda n: sys.argv[sys.argv.index(n) + 1] if n in sys.argv else None
    events = json.load(open("events.json"))["events"]
    found = {}
    # одне джерело може тимчасово не відповідати: решта все одно оновляться
    for name, job in (("tennis", lambda: tennis(events)), ("padel", lambda: padel(events, arg("--test-padel"))),
                      ("esports", lambda: esports(events, arg("--test-lq")))):
        try:
            for m in job():
                found[(m["t"], m["title"], m["tour"])] = m
        except Exception as e:
            print(f"{name} failed: {e}")
    decisive = [m for m in found.values() if m["round"] in BANNER_ROUNDS and abs(m["t"] - time.time()) <= 36 * 3600]
    # у файлі до 12 матчів: завершені не мають витісняти ті, що попереду
    matches = sorted(decisive, key=lambda m: (m["state"] == "post", m["t"]))[:12]
    matches.sort(key=lambda m: m["t"])
    matches = [{k: v for k, v in m.items() if k != "full"} for m in matches]
    today = dt.datetime.now(MADRID).replace(hour=0, minute=0, second=0, microsecond=0)
    first, last = today.timestamp(), (today + dt.timedelta(days=2)).timestamp()
    games, per_tour = [], {}
    for m in sorted(found.values(), key=lambda m: (m["state"] == "post", m["t"])):
        if first <= m["t"] < last and per_tour.get(m["tour"], 0) < MAX_GAMES_PER_TOUR and len(games) < MAX_GAMES:
            per_tour[m["tour"]] = per_tour.get(m["tour"], 0) + 1
            games.append({**{k: v for k, v in m.items() if k != "title"}})
    games.sort(key=lambda m: m["t"])
    try:
        saved = json.load(open("matches.json"))
    except (OSError, ValueError):
        saved = {}
    changed = saved.get("matches") != matches or saved.get("games") != games
    if changed:
        with open("matches.json", "w") as f:
            json.dump({"updated": int(time.time()), "matches": matches, "games": games}, f, indent=1)
    print(f"matches {len(matches)}, games {len(games)}, changed {changed}")
    for m in matches:
        print(" ", dt.datetime.fromtimestamp(m["t"]).strftime("%d.%m %H:%M"), m["state"], m["round"], m["title"], "|", m["tour"])
    for m in games:
        print("  g", dt.datetime.fromtimestamp(m["t"]).strftime("%d.%m %H:%M"), m["state"], m["round"], m["full"], "|", m["tour"], "tbc" if m.get("tbc") else "")


if __name__ == "__main__":
    main()
