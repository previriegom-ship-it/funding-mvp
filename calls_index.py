"""Sector-indexed cache of Horizon Europe calls.

Build the index once (downloads from SEDIA API):
    python calls_index.py
    python calls_index.py 300   # fetch up to 300 calls

Query at runtime:
    from calls_index import search_calls
    calls = search_calls("DIGITAL_TECH", [{"sector": "SECURITY_DEFENCE"}])
"""

import json
from datetime import datetime
from pathlib import Path

from sector_mapping import SECTORS, _normalize_text
from logger import get_logger

logger = get_logger("calls_index")

INDEX_PATH = Path("calls_index.json")


def _classify_call_sector(call: dict) -> str:
    """Return the best-matching sector code for a call, or 'UNKNOWN'."""
    text = " ".join([call.get("TÍTULO", ""), call.get("SCOPE", "")])
    normalized = _normalize_text(text)

    best_sector: str | None = None
    best_score = 0

    for sector_code, sector_def in SECTORS.items():
        req = sum(1 for kw in sector_def["required"] if kw in normalized)
        opt = sum(1 for kw in sector_def["optional"] if kw in normalized)
        score = req * 2 + opt
        if score > best_score:
            best_score = score
            best_sector = sector_code

    return best_sector if best_score > 0 else "UNKNOWN"


def build_index(max_results: int = 200) -> dict:
    """Download open/forthcoming Horizon Europe calls and index them by sector.

    Saves the result to calls_index.json. Returns the raw index dict
    (keys = sector codes, values = list of call dicts).
    """
    from calls_fetcher import fetch_calls

    logger.info(f"Building call index — fetching up to {max_results} calls from API...")
    calls = fetch_calls(status=("open", "forthcoming"), max_results=max_results)
    logger.info(f"Fetched {len(calls)} calls")

    # One bucket per sector + unknown
    index: dict[str, list] = {code: [] for code in SECTORS}
    index["UNKNOWN"] = []

    for call in calls:
        sector = _classify_call_sector(call)
        index[sector].append(call)

    # Log distribution
    for sector, bucket in index.items():
        if bucket:
            logger.info(f"  {sector}: {len(bucket)} calls")

    wrapped = {
        "_meta": {
            "built_at": datetime.now().isoformat(),
            "total_calls": len(calls),
            "sectors": {k: len(v) for k, v in index.items() if v},
        },
        "index": index,
    }

    INDEX_PATH.write_text(
        json.dumps(wrapped, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(f"Index saved → {INDEX_PATH}")
    return index


def _load_index() -> dict:
    """Load the index from disk.  Raises FileNotFoundError when not built yet."""
    if not INDEX_PATH.exists():
        raise FileNotFoundError(
            f"{INDEX_PATH} does not exist. Build it first: python calls_index.py"
        )
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    # Support both the wrapped {"_meta":…, "index":…} format and a raw dict
    return data.get("index", data)


def search_calls(
    primary_sector: str | None,
    secondary_sectors: list | None,
    top_n: int = 10,
) -> list[dict]:
    """Return candidate calls for matching, ordered by sector relevance.

    Fills slots in this priority order:
      1. All calls from primary_sector
      2. All calls from each secondary_sector (in order)
      3. UNKNOWN bucket as fallback if still below top_n candidates

    The function never filters by score — it returns complete call objects so
    the scorer in matcher.py can rank them properly.

    Args:
        primary_sector: sector code (e.g. "DIGITAL_TECH") or None
        secondary_sectors: list of dicts with a "sector" key, or list of str
        top_n: soft guide — stop adding secondary/unknown buckets once we have
               at least this many candidates (primary bucket is always included whole)

    Returns:
        List of call dicts compatible with matcher.score_call()
    """
    index = _load_index()

    # Normalize secondary sectors to a list of code strings
    sec_codes: list[str] = []
    if secondary_sectors:
        for s in secondary_sectors:
            if isinstance(s, dict):
                code = s.get("sector", "")
            else:
                code = str(s)
            if code and code != primary_sector:
                sec_codes.append(code)

    result: list[dict] = []
    seen_ids: set[str] = set()

    def _add_bucket(sector_code: str) -> None:
        bucket = index.get(sector_code, [])
        for call in bucket:
            cid = call.get("ID", "")
            if cid not in seen_ids:
                seen_ids.add(cid)
                result.append(call)

    # 1. Primary sector (always fully included)
    if primary_sector:
        _add_bucket(primary_sector)
        logger.debug(f"Primary {primary_sector}: {len(result)} calls")

    # 2. Secondary sectors until we have enough candidates
    for code in sec_codes:
        if len(result) >= top_n * 3:  # 3× gives the scorer plenty to work with
            break
        before = len(result)
        _add_bucket(code)
        logger.debug(f"Secondary {code}: +{len(result) - before} calls")

    # 3. UNKNOWN fallback if we're still light on candidates
    if len(result) < top_n:
        before = len(result)
        _add_bucket("UNKNOWN")
        logger.debug(f"UNKNOWN fallback: +{len(result) - before} calls")

    logger.info(
        f"search_calls → {len(result)} candidates "
        f"(primary={primary_sector}, secondary={sec_codes})"
    )
    return result


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    build_index(max_results=n)
    print(f"\nIndex built successfully. Run the API and test with your research group URL.")
