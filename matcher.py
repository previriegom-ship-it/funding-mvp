"""Match an organization profile against funding calls.

Reads a profile (JSON, as produced by profiler.generate_profile / analyze_group),
scores calls against it, and returns results in one of four detail levels:

    "quick"   -> list[dict]           — top-N only (backward-compatible)
    "sectors" -> dict                 — top-N + per-sector breakdowns
    "full"    -> dict                 — sectors + all_ranked (default)
    "all"     -> dict                 — same as full, explicit alias
"""

import json
import re
from sector_mapping import SECTORS, _normalize_text
from logger import get_logger

logger = get_logger("matcher")


# ---------------------------------------------------------------------------
# Parsing utilities
# ---------------------------------------------------------------------------

def parse_calls(path: str = "calls.txt") -> list[dict]:
    """Parse a calls.txt file into a list of call dicts keyed by field label."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    calls = []
    for block in re.split(r"^\s*---\s*$", raw, flags=re.MULTILINE):
        block = block.strip()
        if not block:
            continue
        fields = {}
        for line in block.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip().upper()] = value.strip()
        if fields:
            calls.append(fields)
    return calls


def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, dropping very short/common noise words."""
    stop = {
        "de", "la", "el", "los", "las", "y", "en", "a", "para", "con", "del",
        "the", "of", "and", "to", "for", "in", "on", "an", "as",
    }
    words = re.findall(r"[a-záéíóúñ0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in stop}


# ---------------------------------------------------------------------------
# Profile-weight building
# ---------------------------------------------------------------------------

# Relative weight of each profile section. Core topics carry the most weight;
# the group name is kept low so generic words don't inflate scores.
SECTION_WEIGHTS = {
    "primary_keywords":     1.0,
    "technologies_developed": 1.0,
    "technical_capabilities": 1.0,
    "research_line_keywords": 0.9,
    "application_domains":  0.8,
    "secondary_keywords":   0.6,
    "interdisciplinary_topics": 0.6,
    "explanation":          0.4,
    "name":                 0.15,
}


def _weighted_profile_terms(profile: dict) -> dict[str, float]:
    """Map each profile term to its max weight across all sections."""
    research_line_keywords: list[str] = []
    for line in profile.get("research_lines", []) or []:
        research_line_keywords.append(line.get("name", ""))
        research_line_keywords.extend(line.get("keywords", []) or [])

    sections = {
        "primary_keywords":       profile.get("primary_keywords", []) or [],
        "technologies_developed": profile.get("technologies_developed", []) or [],
        "technical_capabilities": profile.get("technical_capabilities", []) or [],
        "research_line_keywords": research_line_keywords,
        "application_domains":    profile.get("application_domains", []) or [],
        "secondary_keywords":     profile.get("secondary_keywords", []) or [],
        "interdisciplinary_topics": profile.get("interdisciplinary_topics", []) or [],
        "explanation":            [profile.get("explanation", "")],
        "name":                   [profile.get("name", "")],
    }
    weights: dict[str, float] = {}
    for section, texts in sections.items():
        w = SECTION_WEIGHTS.get(section, 0.5)
        for term in _tokenize(" ".join(texts)):
            weights[term] = max(weights.get(term, 0.0), w)
    return weights


# ---------------------------------------------------------------------------
# Single-call scoring
# ---------------------------------------------------------------------------

def classify_status(estado: str) -> str:
    """Normalize ESTADO into: "Abierta" | "Próximamente" | "Cerrada"."""
    e = estado.lower()
    if "cerrada" in e:
        return "Cerrada"
    if "abierta" in e:
        return "Abierta" if e.strip() == "abierta" else "Próximamente"
    return "Próximamente"


def get_call_sector(call: dict) -> str:
    """Return the best-matching sector code for a call, or "UNKNOWN"."""
    call_text = " ".join([call.get("TÍTULO", ""), call.get("SCOPE", "")])
    normalized = _normalize_text(call_text)

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


def score_call(
    profile_weights: dict[str, float],
    call: dict,
    profile: dict | None = None,
) -> tuple[float, str]:
    """Score a call by weighted keyword overlap with the profile.

    Returns (score, sector_match) where sector_match is
    "primary" | "secondary" | "none".
    """
    call_text = " ".join([call.get("TÍTULO", ""), call.get("SCOPE", "")])
    call_terms = _tokenize(call_text)
    if not call_terms:
        return 0.0, "none"

    matched_weight = sum(profile_weights[t] for t in call_terms if t in profile_weights)
    base_score = matched_weight / len(call_terms)

    sector_match = "none"
    multiplier = 0.7  # default: sector mismatch

    if profile:
        call_sector = get_call_sector(call)
        primary_sector = profile.get("primary_sector")
        secondary_codes = [
            s.get("sector") for s in profile.get("secondary_sectors", [])
        ]
        if call_sector != "UNKNOWN":
            if call_sector == primary_sector:
                multiplier = 1.2
                sector_match = "primary"
            elif call_sector in secondary_codes:
                multiplier = 1.0
                sector_match = "secondary"

    return round(base_score * multiplier, 4), sector_match


# ---------------------------------------------------------------------------
# Call sources
# ---------------------------------------------------------------------------

def get_relevant_calls(profile: dict) -> list[dict]:
    """Return sector-relevant calls for a profile from the sector index.

    Falls back to calls_live.txt when the index has not been built yet.
    """
    from calls_index import search_calls

    primary = profile.get("primary_sector")
    secondary = profile.get("secondary_sectors", [])

    try:
        calls = search_calls(primary, secondary, top_n=10)
        logger.info(f"Index lookup: {len(calls)} candidate calls for sector={primary}")
        return calls
    except FileNotFoundError:
        logger.warning("calls_index.json not found — falling back to calls_live.txt")
        return parse_calls("calls_live.txt")


def _get_all_index_calls() -> list[dict]:
    """Return every call in the sector index (all buckets combined).

    Falls back to calls_live.txt when the index has not been built yet.
    """
    from calls_index import _load_index

    try:
        index = _load_index()
        all_calls: list[dict] = []
        seen_ids: set[str] = set()
        for bucket in index.values():
            for call in bucket:
                cid = call.get("ID", "")
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    all_calls.append(call)
        logger.info(f"Loaded {len(all_calls)} total calls from full index (deduplicated)")
        return all_calls
    except FileNotFoundError:
        logger.warning("calls_index.json not found — falling back to calls_live.txt")
        return parse_calls("calls_live.txt")


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

def _score_all_raw(
    profile_weights: dict[str, float],
    calls: list[dict],
    profile: dict,
) -> list[dict]:
    """Score every non-closed call and return them sorted by score (desc).

    Each result dict includes:
        id, title, status, deadline, score, sector_match, call_sector
    """
    scored: list[dict] = []
    closed_count = 0
    tallies = {"primary": 0, "secondary": 0, "none": 0}

    for call in calls:
        status = classify_status(call.get("ESTADO", ""))
        if status == "Cerrada":
            closed_count += 1
            continue

        score, sector_match = score_call(profile_weights, call, profile)
        call_sector = get_call_sector(call)
        tallies[sector_match] += 1

        scored.append({
            "id":           call.get("ID", "?"),
            "title":        call.get("TÍTULO", ""),
            "status":       status,
            "deadline":     call.get("DEADLINE", ""),
            "score":        score,
            "sector_match": sector_match,
            "call_sector":  call_sector,
            "scope":        call.get("SCOPE", ""),
        })

    if closed_count:
        logger.debug(f"Skipped {closed_count} closed calls")

    logger.info(
        f"Scored {len(scored)} calls — "
        f"primary: {tallies['primary']}, "
        f"secondary: {tallies['secondary']}, "
        f"none: {tallies['none']}"
    )

    scored.sort(key=lambda c: c["score"], reverse=True)
    if scored:
        logger.info(f"Top score: {scored[0]['score']:.4f} ({scored[0]['id']})")

    return scored


# ---------------------------------------------------------------------------
# Multi-view ranking
# ---------------------------------------------------------------------------

def get_ranked_opportunities(
    profile: dict,
    calls_scored: list[dict],
    top_n: int = 10,
) -> dict:
    """Build the three-view ranking structure from a pre-scored calls list.

    Views returned:
        top_10_general  — top_n calls sorted by score (any sector)
        by_sector       — primary top-5 + secondary top-3 per sector
        all_ranked      — every scored call (sorted, no truncation)

    Args:
        profile:      Profile dict with primary_sector / secondary_sectors.
        calls_scored: Output of _score_all_raw() — sorted, scored call dicts.
        top_n:        Size of the general top list (default 10).
    """
    primary_sector = profile.get("primary_sector")
    primary_label  = profile.get("primary_sector_label", "")
    secondary_sectors = profile.get("secondary_sectors", [])

    # Top-N general (no sector filter)
    top_general = calls_scored[:top_n]

    # Primary sector: calls where the call itself belongs to the primary sector
    primary_calls = [c for c in calls_scored if c["sector_match"] == "primary"]

    # Secondary sectors: top-3 per sector code
    secondary_views: dict[str, dict] = {}
    for sec in secondary_sectors:
        if isinstance(sec, dict):
            sec_code  = sec.get("sector", "")
            sec_label = sec.get("label", "")
        else:
            sec_code  = str(sec)
            sec_label = ""
        if not sec_code:
            continue
        sec_calls = [c for c in calls_scored if c.get("call_sector") == sec_code]
        secondary_views[sec_code] = {
            "sector_code":  sec_code,
            "sector_label": sec_label,
            "top_3":        sec_calls[:3],
        }

    logger.info(
        f"get_ranked_opportunities — "
        f"top_general: {len(top_general)}, "
        f"primary_pool: {len(primary_calls)}, "
        f"secondary_sectors: {len(secondary_views)}, "
        f"all: {len(calls_scored)}"
    )

    return {
        "top_10_general": top_general,
        "by_sector": {
            "primary": {
                "sector_code":  primary_sector,
                "sector_label": primary_label,
                "top_5":        primary_calls[:5],
            },
            "secondary": secondary_views,
        },
        "all_ranked": calls_scored,
    }


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------

def match(
    profile: dict,
    calls: list | None = None,
    top_n: int = 10,
    detail_level: str = "full",
) -> "list[dict] | dict":
    """Score calls against the profile and return ranked opportunities.

    Args:
        profile:      Research group profile dict (with sector classification).
        calls:        Pre-loaded call list. When None the source is chosen
                      automatically: all-index for full/all, sector-filtered
                      for quick/sectors.
        top_n:        Number of calls in the general top list (default 10).
        detail_level: Output depth:
                      "quick"   → list[dict] — top_n only (backward-compat)
                      "sectors" → dict(top_10_general, by_sector)
                      "full"    → dict(top_10_general, by_sector, all_ranked)
                      "all"     → same as "full" (explicit alias)

    Returns:
        list[dict] for "quick"; structured dict for all other levels.
    """
    profile_weights = _weighted_profile_terms(profile)

    if calls is None:
        if detail_level in ("full", "all"):
            calls = _get_all_index_calls()
        else:
            calls = get_relevant_calls(profile)

    logger.info(f"match() — {len(calls)} calls to score (detail_level={detail_level!r})")
    calls_scored = _score_all_raw(profile_weights, calls, profile)

    # ── quick: flat list, backward-compatible ──────────────────────────────
    if detail_level == "quick":
        return calls_scored[:top_n]

    # ── build the structured multi-view result ─────────────────────────────
    ranked = get_ranked_opportunities(profile, calls_scored, top_n=top_n)

    if detail_level == "sectors":
        return {
            "top_10_general": ranked["top_10_general"],
            "by_sector":      ranked["by_sector"],
        }

    # "full" or "all"
    return ranked


# ---------------------------------------------------------------------------
# Helpers / CLI
# ---------------------------------------------------------------------------

def load_profile(path: str) -> dict:
    """Load a profile JSON file from disk."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        profile = load_profile(sys.argv[1])
    else:
        from profiler import analyze_group
        profile = analyze_group("https://ging.github.io/")

    results = match(profile, detail_level="quick")
    print(f"Top {len(results)} opportunities for: {profile.get('name', 'organization')}\n")
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['score']}] {r['status'].upper()} — {r['id']}")
        print(f"   {r['title']}")
        print(f"   deadline: {r['deadline']}\n")
