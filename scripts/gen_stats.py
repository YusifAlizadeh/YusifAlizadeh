#!/usr/bin/env python3
"""Render assets/stats.svg from live GitHub data.

The public github-readme-stats instance answers 503 often enough that the
profile looked broken, so the card is generated here and committed instead.
Needs GITHUB_TOKEN (any token that can read public user data) and GH_LOGIN.
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"
LOGIN = os.environ.get("GH_LOGIN", "YusifAlizadeh")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "stats.svg")

BG, PANEL, ACCENT, ALERT, AMBER, TEXT, DIM, EMPTY = (
    "#0a0c10", "#0d1117", "#00ff9c", "#ff2a4d", "#ffb000", "#c9d1d9", "#6e7681", "#1b2129",
)

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def fetch(token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": f"{LOGIN}-profile-stats"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def streaks(days):
    """Current and longest run of consecutive days with contributions.

    Today is excluded from breaking the current streak: a day that has not
    happened yet should not reset a streak that is still alive.
    """
    today = date.today()
    counts = {d["date"]: d["contributionCount"] for d in days}
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] > 0 else 0
        longest = max(longest, run)

    cur = 0
    cursor = today
    if counts.get(cursor.isoformat(), 0) == 0:
        cursor -= timedelta(days=1)
    while counts.get(cursor.isoformat(), 0) > 0:
        cur += 1
        cursor -= timedelta(days=1)
    return cur, longest


def top_languages(repos, limit=5):
    totals = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            totals[edge["node"]["name"]] = totals.get(edge["node"]["name"], 0) + edge["size"]
    total = sum(totals.values())
    if not total:
        return []
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [(name, size * 100.0 / total) for name, size in ranked]


def meter(x, y, filled, segments=10, w=14, gap=3, h=12):
    out = []
    for i in range(segments):
        fill = ACCENT if i < filled else EMPTY
        out.append(f'<rect x="{x + i * (w + gap)}" y="{y}" width="{w}" height="{h}" rx="2" fill="{fill}"/>')
    return "".join(out)


def build(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [d for week in cal["weeks"] for d in week["contributionDays"]]
    cur, longest = streaks(days)
    repos = user["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    langs = top_languages(repos)

    rows = [
        ("contributions (1y)", f'{cal["totalContributions"]}', ACCENT),
        ("commits (1y)", f'{user["contributionsCollection"]["totalCommitContributions"]}', TEXT),
        ("current streak", f"{cur} day{'s' if cur != 1 else ''}", ALERT),
        ("longest streak", f"{longest} day{'s' if longest != 1 else ''}", TEXT),
        ("public repos", f'{user["repositories"]["totalCount"]}', TEXT),
        ("stars earned", f"{stars}", AMBER),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 300" width="900" height="300"',
        ' preserveAspectRatio="xMidYMid meet" role="img" aria-label="GitHub statistics">',
        "<title>./stats --theme=dark</title>",
        '<defs><pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">',
        f'<rect x="0" y="0" width="4" height="2" fill="#000000" opacity="0.10"/></pattern></defs>',
        "<g font-family=\"ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'DejaVu Sans Mono', monospace\">",
        f'<rect x="0" y="0" width="900" height="300" rx="10" fill="{BG}"/>',
        f'<text x="28" y="40" font-size="15" fill="{ACCENT}">┌──(root㉿alizadah)-[~]</text>',
        f'<text x="28" y="64" font-size="15"><tspan fill="{ACCENT}">└─$ </tspan>'
        f'<tspan fill="{TEXT}">./stats --theme=dark</tspan></text>',
    ]

    # left column — counters
    y = 106
    for label, value, color in rows:
        dots = "." * max(2, 24 - len(label))
        parts.append(f'<text x="44" y="{y}" font-size="13" fill="{DIM}">{escape(label)} {dots}</text>')
        parts.append(f'<text x="300" y="{y}" font-size="13" fill="{color}" text-anchor="end">{escape(value)}</text>')
        y += 28

    # right column — language mix
    parts.append(f'<text x="470" y="106" font-size="13" fill="{DIM}">top languages</text>')
    y = 138
    for name, pct in langs:
        parts.append(f'<text x="470" y="{y}" font-size="13" fill="{TEXT}">{escape(name)}</text>')
        parts.append(meter(620, y - 11, max(1, round(pct / 10))))
        parts.append(f'<text x="872" y="{y}" font-size="12" fill="{DIM}" text-anchor="end">{pct:.1f}%</text>')
        y += 28

    stamp = date.today().isoformat()
    parts.append(f'<text x="44" y="282" font-size="11" fill="{DIM}">last sync: {stamp} · generated from the GitHub API</text>')
    parts.append('<rect x="0" y="0" width="900" height="300" rx="10" fill="url(#scan)"/>')
    parts.append(f'<rect x="0.75" y="0.75" width="898.5" height="298.5" rx="10" fill="none" stroke="{ACCENT}" stroke-opacity="0.22" stroke-width="1.5"/>')
    parts.append("</g></svg>")
    return "\n".join(parts) + "\n"


def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    svg = build(fetch(token))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUT} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
