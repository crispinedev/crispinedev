"""Build an animated "most used languages" card for the profile README.

Sums GitHub's per-repo language bytes across the owner's public, non-fork,
non-archived repos. GitHub's numbers honour `linguist-vendored` in each repo's
.gitattributes, so third-party code marked there is left out.

Usage: python languages.py <github-user> <output.svg>
Set GITHUB_TOKEN to avoid the unauthenticated rate limit.
"""

import json
import os
import sys
import urllib.request
from html import escape

TOP_N = 6
WIDTH, HEIGHT = 495, 195
BAR_X, BAR_W = 25, 445

# Mostly GitHub linguist colours; Python, PLpgSQL and PHP are swapped for
# profile-palette colours so they don't read as three near-identical blues next
# to TypeScript. Anything else falls back to the palette.
COLORS = {
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Python": "#D97757",
    "PHP": "#8892BF",
    "CSS": "#9B6FD6",
    "SCSS": "#C6538C",
    "Less": "#1D365D",
    "HTML": "#E34C26",
    "PLpgSQL": "#6FB7A7",
    "Shell": "#89E051",
    "Hack": "#878787",
}
FALLBACK = ["#F5B942", "#6FB7A7", "#D97757", "#9B8AFB", "#E6E1D6", "#8A93A6"]


def get(url, token):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-languages-card",
    })
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def collect(user, token):
    # The workflow's own GITHUB_TOKEN only sees public repos. With a personal
    # access token (the optional LANGS_TOKEN secret) private repos count too;
    # only language totals are published, never repo names.
    if os.environ.get("INCLUDE_PRIVATE") == "true":
        listing = "https://api.github.com/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}"
    else:
        listing = "https://api.github.com/users/" + user + "/repos?type=owner&per_page=100&page={page}"
    totals = {}
    page = 1
    while True:
        repos = get(listing.format(page=page), token)
        if not repos:
            break
        for repo in repos:
            # skip forks, archives, and the profile repo itself (it only holds this script)
            if repo["fork"] or repo["archived"] or repo["name"].lower() == user.lower():
                continue
            for lang, size in get(repo["languages_url"], token).items():
                totals[lang] = totals.get(lang, 0) + size
        page += 1
    return totals


def top_languages(totals):
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(totals.values()) or 1
    rows = [(name, size / total * 100) for name, size in ranked[:TOP_N]]
    rest = sum(size for _, size in ranked[TOP_N:])
    if rest:
        rows[-1:] = [("Other", (ranked[TOP_N - 1][1] + rest) / total * 100)]
    return rows


def render(rows):
    spare = iter(FALLBACK)
    colors = [COLORS.get(name) or next(spare, "#8A93A6") for name, _ in rows]

    segments, x = [], float(BAR_X)
    for (name, pct), color in zip(rows, colors):
        w = BAR_W * pct / 100
        segments.append(f'<rect x="{x:.2f}" y="58" width="{w + 0.5:.2f}" height="10" fill="{color}"/>')
        x += w

    items = []
    for i, ((name, pct), color) in enumerate(zip(rows, colors)):
        col, row = i % 2, i // 2
        ix, iy = 25 + col * 235, 102 + row * 32
        items.append(
            f'<g class="item" style="animation-delay:{0.5 + i * 0.12:.2f}s">'
            f'<circle cx="{ix + 5}" cy="{iy - 4}" r="5" fill="{color}"/>'
            f'<text x="{ix + 18}" y="{iy}" class="sans ink" font-size="13">{escape(name)}</text>'
            f'<text x="{ix + 205}" y="{iy}" text-anchor="end" class="mono dim" font-size="12">{pct:.1f}%</text>'
            f'</g>'
        )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="Most used languages: {escape(", ".join(f"{n} {p:.1f}%" for n, p in rows))}">
  <style>
    .sans {{ font-family: "Segoe UI", -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; }}
    .mono {{ font-family: ui-monospace, "SFMono-Regular", "Cascadia Code", Menlo, Consolas, monospace; }}
    .ink {{ fill: #F2EFE9; }} .dim {{ fill: #8A93A6; }} .amber {{ fill: #F5B942; }}
    .item {{ animation: rise .6s ease-out both; }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
    @media (prefers-reduced-motion: reduce) {{ .item {{ animation: none; }} }}
  </style>
  <defs>
    <clipPath id="bar">
      <rect x="{BAR_X}" y="58" width="{BAR_W}" height="10" rx="5">
        <animate attributeName="width" from="0" to="{BAR_W}" dur="1.2s" calcMode="spline" keySplines=".2 .7 .2 1" keyTimes="0;1" fill="freeze"/>
      </rect>
    </clipPath>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" rx="12" fill="#0B1220"/>
  <text x="25" y="38" class="mono amber" font-size="13" letter-spacing="2.5">MOST USED LANGUAGES</text>
  <rect x="{BAR_X}" y="58" width="{BAR_W}" height="10" rx="5" fill="#1A2436"/>
  <g clip-path="url(#bar)">{"".join(segments)}</g>
  {"".join(items)}
</svg>
'''


def main():
    user, out = sys.argv[1], sys.argv[2]
    rows = top_languages(collect(user, os.environ.get("GITHUB_TOKEN", "")))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(rows))
    for name, pct in rows:
        print(f"{name:12} {pct:5.1f}%")


if __name__ == "__main__":
    main()
