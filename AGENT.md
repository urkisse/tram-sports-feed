# Weekly sports feed — instructions for the agent

You maintain `events.json` in this repository. A small home display (ESP32 board) downloads it every few hours
and shows the next top sports events on its third page. Run once a week (Monday morning).

## What to include (next ~6 weeks from today, Europe/Madrid time)

The owner lives in Spain and only wants the **top** events. Be strict: 6–12 events in total is ideal.
Only three sports: padel, boxing, tennis. **No football and no table tennis** (the owner removed them).

- **padel** — Premier Padel: every Major and P1 tournament, plus the season Finals. Final-day matches are a bonus
  (one entry for the tournament with its date range is enough). P2 only if nothing else that week.
- **boxing** — only major fights: undisputed or unified world title fights, and mega-fights of the biggest
  names (pound-for-pound top 10, e.g. Canelo, Usyk, Inoue, Crawford level). Use the main-event ring-walk time
  if known, else the card start time.
- **tennis** — Grand Slams, ATP/WTA Finals, Davis Cup Finals, Billie Jean King Cup Finals, ATP Masters 1000
  (and WTA 1000 that run combined with them). One entry per tournament with its date range.

Never invent events or times. Only use dates you found on an official or reliable source (league, federation,
tour or promoter site, major sports media). If a time is not announced yet, use 12:00 local and set `"tbc": true`.
Drop events that already ended. Keep events that are in progress.

## File format (`events.json`)

```json
{
  "updated": 1793548800,
  "events": [
    { "sport": "boxing", "t": 1794081600, "title": "Fury v Joshua", "sub": "Heavyweight - Cardiff" },
    { "sport": "tennis", "t": 1793865600, "end": 1794470400, "title": "ATP Finals", "sub": "Turin" }
  ]
}
```

- `updated` — Unix time (seconds, UTC) when you wrote the file.
- `sport` — one of `padel`, `boxing`, `tennis`.
- `t` — start, Unix time in seconds (UTC). For a match/fight: the start time. For a tournament: 00:00 Madrid time of day 1.
- `end` — only for multi-day tournaments: 23:59 Madrid time of the last day.
- `title` — at most 22 characters, plain ASCII (no accents: Clasico, Atletico, Malaga). Names, not descriptions:
  "Canelo v Crawford", "Milano P1", "WTT Finals", "Australian Open".
- `sub` — at most 30 characters, plain ASCII: competition and place, e.g. "Heavyweight - Cardiff", "Premier Padel - Milan".
- `tbc` — optional `true` when the time is not confirmed.
- Sort by `t`. At most 20 events. The board shows the 6 nearest that have not finished.

## Steps

1. Search the web for each sport's schedule for the next 6 weeks; verify dates on at least one reliable source.
2. Write `events.json` exactly in the format above (validate it: `python3 -m json.tool events.json`;
   check every title is <= 22 chars and ASCII).
3. Commit only that file with the message `feed: update sports events (YYYY-MM-DD)` and push to `main`.
4. In your final message list the events you added and anything you were unsure about.
