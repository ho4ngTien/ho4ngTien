#!/usr/bin/env python3
"""
Generate activity-graph SVGs (light + dark) from GitHub's GraphQL API.
Requires: GITHUB_TOKEN env var (read-only public access is enough).
Output:   assets/readme/activity-graph-light.svg
          assets/readme/activity-graph-dark.svg
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME = os.environ.get("GRAPH_USERNAME", "ho4ngTien")
TOKEN    = os.environ.get("GITHUB_TOKEN", "")
OUT_DIR  = os.environ.get("ASSETS_DIR", "assets/readme")

# ── Themes ────────────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg":          "#ffffff",
        "border":      "#e1e4e8",
        "title":       "#24292e",
        "label":       "#586069",
        "line":        "#0969da",
        "line_fill":   "#dbeafe",
        "dot":         "#0969da",
        "grid":        "#e1e4e8",
        "area_stop":   "#ffffff",
    },
    "dark": {
        "bg":          "#1a1b26",
        "border":      "#30363d",
        "title":       "#70a5fd",
        "label":       "#8b949e",
        "line":        "#70a5fd",
        "line_fill":   "#1e3a5f",
        "dot":         "#70a5fd",
        "grid":        "#21262d",
        "area_stop":   "#1a1b26",
    },
}

# ── GraphQL query ─────────────────────────────────────────────────────────────
QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_contributions(username: str, token: str) -> list:
    """Return list of {date, count} for the past ~12 months."""
    now  = datetime.now(timezone.utc)
    frm  = now.replace(year=now.year - 1).strftime("%Y-%m-%dT%H:%M:%SZ")
    to   = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = json.dumps({
        "query": QUERY,
        "variables": {"login": username, "from": frm, "to": to},
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "User-Agent":   "generate-activity-graph/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request("https://api.github.com/graphql", data=payload, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except URLError as exc:
        print(f"Error fetching GitHub data: {exc}", file=sys.stderr)
        sys.exit(1)

    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}", file=sys.stderr)
        sys.exit(1)

    weeks = (
        data["data"]["user"]
        ["contributionsCollection"]
        ["contributionCalendar"]
        ["weeks"]
    )
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append({"date": day["date"], "count": day["contributionCount"]})
    return days


def weekly_totals(days: list) -> list:
    weeks = []
    for i in range(0, len(days), 7):
        weeks.append(sum(d["count"] for d in days[i : i + 7]))
    return weeks


def month_labels(days: list, n_weeks: int, x_start: float, x_end: float) -> list:
    labels = []
    seen_months = set()
    for i, day in enumerate(days[::7]):
        week_idx = i
        month = day["date"][5:7]
        if month not in seen_months:
            seen_months.add(month)
            x = x_start + (week_idx / max(n_weeks - 1, 1)) * (x_end - x_start)
            labels.append((datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b"), x))
    return labels


W, H       = 1200, 280
PAD_L      = 48
PAD_R      = 24
PAD_T      = 54
PAD_B      = 36
GRID_LINES = 4


def smooth_path(values: list, x0: float, x1: float, y0: float, y1: float) -> str:
    if len(values) < 2:
        return ""
    max_v = max(values) or 1
    n     = len(values)

    def pt(i):
        x = x0 + i / (n - 1) * (x1 - x0)
        y = y1 - (values[i] / max_v) * (y1 - y0)
        return x, y

    parts = ["M {:.2f} {:.2f}".format(*pt(0))]
    for i in range(1, n):
        x1p, y1p = pt(i - 1)
        x2p, y2p = pt(i)
        cp1x = x1p + (x2p - x1p) / 3
        cp2x = x1p + 2 * (x2p - x1p) / 3
        parts.append("C {:.2f} {:.2f}, {:.2f} {:.2f}, {:.2f} {:.2f}".format(
            cp1x, y1p, cp2x, y2p, x2p, y2p))
    return " ".join(parts)


def fill_path(s_path: str, x0: float, x1: float, y1: float) -> str:
    return "{} L {:.2f} {:.2f} L {:.2f} {:.2f} Z".format(s_path, x1, y1, x0, y1)


def render_svg(weeks: list, days: list, theme: dict, username: str) -> str:
    x0 = float(PAD_L)
    x1 = float(W - PAD_R)
    y0 = float(PAD_T)
    y1 = float(H - PAD_B)
    n  = len(weeks)
    total = sum(weeks)
    max_v = max(weeks) or 1
    grad_id = "areaGrad"

    grid_svg = ""
    for gi in range(1, GRID_LINES + 1):
        gy  = y1 - (gi / GRID_LINES) * (y1 - y0)
        val = int(max_v * gi / GRID_LINES)
        grid_svg += (
            '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" '
            'stroke="{}" stroke-width="1" stroke-dasharray="4 4"/>\n'
            '<text x="{}" y="{:.1f}" text-anchor="end" '
            'font-size="10" fill="{}">{}</text>\n'
        ).format(x0, gy, x1, gy, theme["grid"], x0 - 4, gy + 4, theme["label"], val)

    grid_svg += (
        '<line x1="{:.1f}" y1="{:.1f}" x2="{:.1f}" y2="{:.1f}" '
        'stroke="{}" stroke-width="1"/>\n'
    ).format(x0, y1, x1, y1, theme["grid"])

    m_labels = month_labels(days, n, x0, x1)
    month_svg = ""
    for label, lx in m_labels:
        month_svg += (
            '<text x="{:.1f}" y="{}" text-anchor="middle" '
            'font-size="11" fill="{}">{}</text>\n'
        ).format(lx, y1 + 16, theme["label"], label)

    s_path = smooth_path(weeks, x0, x1, y0, y1)
    f_path = fill_path(s_path, x0, x1, y1)

    dot_svg = ""
    for i, v in enumerate(weeks):
        dx = x0 + i / max(n - 1, 1) * (x1 - x0)
        dy = y1 - (v / max_v) * (y1 - y0)
        dot_svg += '<circle cx="{:.2f}" cy="{:.2f}" r="3" fill="{}"/>\n'.format(
            dx, dy, theme["dot"])

    svg = (
        '<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        'fill="none" xmlns="http://www.w3.org/2000/svg">\n'
        '  <defs>\n'
        '    <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">\n'
        '      <stop offset="0%" stop-color="{lf}" stop-opacity="0.8"/>\n'
        '      <stop offset="100%" stop-color="{as_}" stop-opacity="0"/>\n'
        '    </linearGradient>\n'
        '    <clipPath id="chartClip">\n'
        '      <rect x="{x0}" y="{y0}" width="{cw}" height="{ch}"/>\n'
        '    </clipPath>\n'
        '  </defs>\n'
        '  <rect width="{W}" height="{H}" rx="12" fill="{bg}"/>\n'
        '  <text x="{cx}" y="30" text-anchor="middle"\n'
        '        font-family="\'Segoe UI\', Ubuntu, sans-serif"\n'
        '        font-size="15" font-weight="600" fill="{tc}">\n'
        '    {user}\'s Contribution Graph  \u00b7  {total:,} contributions in the last year\n'
        '  </text>\n'
        '  {grid}\n'
        '  <path d="{fp}" fill="url(#{gid})" clip-path="url(#chartClip)"/>\n'
        '  <path d="{sp}" stroke="{lc}" stroke-width="2.5"\n'
        '        fill="none" stroke-linejoin="round" stroke-linecap="round"\n'
        '        clip-path="url(#chartClip)"/>\n'
        '  {dots}\n'
        '  {months}\n'
        '</svg>'
    ).format(
        W=W, H=H,
        gid=grad_id,
        lf=theme["line_fill"], as_=theme["area_stop"],
        x0=x0, y0=y0, cw=x1 - x0, ch=y1 - y0,
        bg=theme["bg"],
        cx=W / 2, tc=theme["title"],
        user=username, total=total,
        grid=grid_svg,
        fp=f_path, sp=s_path,
        lc=theme["line"],
        dots=dot_svg, months=month_svg,
    )
    return svg


def main():
    if not TOKEN:
        print("Warning: GITHUB_TOKEN not set; public rate limit applies.", file=sys.stderr)

    print(f"Fetching contributions for {USERNAME}...")
    days  = fetch_contributions(USERNAME, TOKEN)
    weeks = weekly_totals(days)
    print(f"  {len(days)} days -> {len(weeks)} weekly buckets, total={sum(weeks)}")

    os.makedirs(OUT_DIR, exist_ok=True)

    for theme_name, theme in THEMES.items():
        svg  = render_svg(weeks, days, theme, USERNAME)
        path = os.path.join(OUT_DIR, f"activity-graph-{theme_name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"  Written {path}")

    print("Done.")


if __name__ == "__main__":
    main()
