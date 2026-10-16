#!/usr/bin/env python3
"""Check relative links and #anchors in the repository's Markdown files.

    python3 scripts/check-links.py

External (http/https/mailto) links are not fetched. Exit 1 on a broken link.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


def slug(text):
    # GitHub's heading anchors: lowercase, drop punctuation, spaces to '-'.
    text = re.sub(r"`([^`]*)`", r"\1", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def scan(path):
    links, anchors, seen = [], set(), {}
    in_fence = False
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING.match(line)
        if m:
            s = slug(m.group(2))
            k = seen.get(s, 0)
            anchors.add(s if k == 0 else "%s-%d" % (s, k))
            seen[s] = k + 1
        for target in LINK.findall(re.sub(r"`[^`]*`", "", line)):
            links.append((n, target))
    return links, anchors


def main():
    files = [p for p in ROOT.rglob("*.md") if not any(part.startswith(".") for part in p.relative_to(ROOT).parts)]
    cache = {}

    def anchors_of(p):
        if p not in cache:
            cache[p] = scan(p)[1]
        return cache[p]

    bad = 0
    for f in sorted(files):
        links, _ = scan(f)
        for n, target in links:
            if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                continue
            path, _, frag = target.partition("#")
            dest = (f.parent / path).resolve() if path else f
            if not dest.exists():
                print("%s:%d: missing %s" % (f.relative_to(ROOT), n, target))
                bad += 1
                continue
            if frag and dest.suffix == ".md" and frag not in anchors_of(dest):
                print("%s:%d: no anchor #%s in %s" % (f.relative_to(ROOT), n, frag, dest.relative_to(ROOT)))
                bad += 1
    print("links: %d file(s), %s" % (len(files), "%d broken" % bad if bad else "OK"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
