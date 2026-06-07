"""Orchestrator: profile an organization from its website and match it to
funding calls.

Usage:
    python main.py [URL]

If no URL is given, defaults to the GING site.
"""

import sys
from logger import get_logger

from profiler import analyze_group
from matcher import match

logger = get_logger("main")
DEFAULT_URL = "https://ging.github.io/"


def run(url: str) -> None:
    logger.info(f"Starting profiling for: {url}")

    profile = analyze_group(url)

    if "error" in profile:
        logger.error(f"Could not build a profile from {url}: {profile.get('error', '')}")
        return

    name = profile.get("name", "organization")
    results = match(profile)
    logger.info(f"Found {len(results)} matching opportunities")

    print(f"\nProfile: {name}")
    explanation = profile.get("explanation", "")
    if explanation:
        print(f"{explanation}\n")

    if not results:
        print("No open or upcoming opportunities matched.")
        logger.info("No opportunities matched profile")
        return

    print(f"Top {len(results)} opportunities:\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['score']:.4f}] {r['status'].upper()} — {r['id']}")
        print(f"   {r['title']}")
        print(f"   deadline: {r['deadline']}\n")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    run(url)
