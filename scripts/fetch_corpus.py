"""Download project READMEs from GitHub into corpus/.

Usage:
    python scripts/fetch_corpus.py              # fetch all repos into corpus/
    python scripts/fetch_corpus.py --out other/ # different output folder

Uses the GitHub "get README" API, which returns the repo's README whatever it
is called (README.md, readme.md, README.rst ...) and whatever the default
branch is (main or master). Set GITHUB_TOKEN to raise the rate limit
(60 requests/hour without a token is plenty for 8 repos).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OWNER = "Ishani-Shree"
REPOS = [
    "Parakh",
    "Watermark-signal",
    "ShopZone",
    "investment-scam-detector",
    "Energy_Aware_GPU",
    "Reachinbox-scheduler",
    "Diabetes_Risk_Analyser",
    "Underwater_Microplastic_Detection",
]

API = "https://api.github.com/repos/{owner}/{repo}/readme"
RAW_FALLBACK = "https://raw.githubusercontent.com/{owner}/{repo}/HEAD/README.md"


def fetch_readme(session: requests.Session, repo: str) -> str:
    """Return README text for one repo. Raises on failure."""
    resp = session.get(
        API.format(owner=OWNER, repo=repo),
        headers={"Accept": "application/vnd.github.raw+json"},
        timeout=20,
    )
    if resp.status_code == 200:
        return resp.text
    # Fallback (e.g. API rate limit hit): raw file on the default branch.
    raw = session.get(RAW_FALLBACK.format(owner=OWNER, repo=repo), timeout=20)
    if raw.status_code == 200:
        return raw.text
    raise RuntimeError(f"API {resp.status_code}, raw {raw.status_code}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="corpus", help="output folder")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers["User-Agent"] = "pramaan-corpus-fetcher"
    if token := os.getenv("GITHUB_TOKEN"):
        session.headers["Authorization"] = f"Bearer {token}"

    manifest, failures = [], []
    for repo in REPOS:
        try:
            text = fetch_readme(session, repo)
        except Exception as exc:  # report and continue with the others
            print(f"  FAIL  {repo}: {exc}")
            failures.append(repo)
            continue

        path = out / f"{repo}.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        words = len(text.split())
        manifest.append(
            {
                "file": path.name,
                "repo": f"https://github.com/{OWNER}/{repo}",
                "words": words,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
        print(f"  OK    {repo:<36} {words:>6} words")

    (out / "manifest.json").write_text(
        json.dumps(
            {"fetched_at": datetime.now(timezone.utc).isoformat(), "files": manifest},
            indent=2,
        ),
        encoding="utf-8",
    )
    total = sum(m["words"] for m in manifest)
    print(f"\n{len(manifest)}/{len(REPOS)} READMEs saved to {out}/  ({total} words total)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
