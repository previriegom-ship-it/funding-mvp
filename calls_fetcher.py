"""Fetch live Horizon Europe calls from the EU Funding & Tenders Portal.

The portal front-end is an Angular SPA, but it is powered by the public SEDIA
search API. This module queries that API directly and normalizes each result
into the same field schema used by calls.txt / matcher.py:

    ID, TÍTULO, CLUSTER, ESTADO, DEADLINE, BUDGET, SCOPE,
    DESCRIPTION_FULL, BUDGET_OVERVIEW, CONDITIONS, TAGS, OPENING_DATE

The SEDIA API returns rich metadata in every result:
  - descriptionByte  → full HTML with Expected Outcomes + Scope sections
  - budgetOverview   → JSON with expectedGrants, minContribution, maxContribution
  - topicConditions  → eligibility conditions HTML
  - tags             → curated keyword tags
  - startDate        → planned opening date

Usage:
    from calls_fetcher import fetch_calls
    calls = fetch_calls(status=("open", "forthcoming"), max_results=200)

    # or run as a script to write a calls.txt-style file:
    python calls_fetcher.py > live_calls.txt
"""

import json
import re

import httpx

SEARCH_URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "SEDIA"

# Horizon Europe framework programme code in SEDIA.
HORIZON_EUROPE = "43108390"

# SEDIA status codes -> the Spanish status labels matcher.classify_status reads.
STATUS_CODES = {
    "forthcoming": "31094501",
    "open": "31094502",
    "closed": "31094503",
}
STATUS_LABELS = {
    "31094501": "Próximamente",
    "31094502": "Abierta",
    "31094503": "Cerrada",
}


def _first(metadata: dict, key: str, default: str = "") -> str:
    """SEDIA metadata values are single-element lists; pull the first value."""
    val = metadata.get(key)
    if isinstance(val, list):
        return str(val[0]) if val else default
    return str(val) if val is not None else default


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _format_deadline(raw: str) -> str:
    # "2026-09-15T00:00:00.000+0000" -> "2026-09-15"
    return raw.split("T", 1)[0] if raw else ""


def fetch_calls(
    status=("open", "forthcoming"),
    max_results: int = 100,
    text: str = "***",
    page_size: int = 50,
    timeout: float = 60.0,
) -> list[dict]:
    """Fetch Horizon Europe call topics, normalized to the calls.txt schema.

    Args:
        status: which statuses to include (any of "open", "forthcoming", "closed").
        max_results: cap on total calls returned (paginates as needed).
        text: free-text query; "***" matches everything.
        page_size: results per API page.
    """
    status_codes = [STATUS_CODES[s] for s in status if s in STATUS_CODES]
    if not status_codes:
        raise ValueError(f"No valid status in {status!r}; choose from {list(STATUS_CODES)}")

    query = {
        "bool": {
            "must": [
                {"terms": {"type": ["1"]}},  # 1 = call topics
                {"terms": {"status": status_codes}},
                {"term": {"frameworkProgramme": HORIZON_EUROPE}},
            ]
        }
    }

    calls: list[dict] = []
    page = 1
    while len(calls) < max_results:
        files = {
            "query": ("query.json", json.dumps(query), "application/json"),
            "languages": ("languages.json", json.dumps(["en"]), "application/json"),
        }
        params = {
            "apiKey": API_KEY,
            "text": text,
            "pageSize": str(page_size),
            "pageNumber": str(page),
        }

        resp = httpx.post(SEARCH_URL, params=params, files=files, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        if not results:
            break

        for res in results:
            md = res.get("metadata", {})
            status_code = _first(md, "status")
            budget = _first(md, "budget")
            currency = _first(md, "currency")

            # descriptionByte is the richest scope source: full HTML with
            # "Expected Outcome:" and "Scope:" sections.  Fall back to the
            # old destination fields when it is absent.
            description_html = _first(md, "descriptionByte")
            if description_html:
                scope = _strip_html(description_html)
            else:
                scope = " ".join(
                    _strip_html(part)
                    for part in (
                        res.get("summary", ""),
                        _first(md, "destinationDescription"),
                        _first(md, "destinationDetails"),
                    )
                    if part
                ).strip()

            # budgetOverview: raw JSON string with per-action budget details
            budget_overview = _first(md, "budgetOverview")

            # topicConditions: eligibility + general conditions HTML
            conditions_html = _first(md, "topicConditions")

            # tags: curated keyword list (already plain strings)
            tags = md.get("tags", [])

            # startDate: planned opening date
            opening_date = _format_deadline(_first(md, "startDate"))

            calls.append(
                {
                    "ID": _first(md, "identifier") or res.get("reference", "?"),
                    "TÍTULO": res.get("title") or _first(md, "title"),
                    "CLUSTER": _first(md, "programmePeriod"),
                    "ESTADO": STATUS_LABELS.get(status_code, status_code),
                    "DEADLINE": _format_deadline(_first(md, "deadlineDate")),
                    "BUDGET": f"{budget} {currency}".strip() if budget else "",
                    "ACTION": _first(md, "typesOfAction"),
                    "SCOPE": scope,
                    "URL": res.get("url", ""),
                    # Rich fields from SEDIA metadata
                    "DESCRIPTION_HTML": description_html,
                    "BUDGET_OVERVIEW": budget_overview,
                    "CONDITIONS_HTML": conditions_html,
                    "TAGS": tags,
                    "OPENING_DATE": opening_date,
                }
            )
            if len(calls) >= max_results:
                break

        # Stop if we've consumed every available result.
        total = data.get("totalResults", 0)
        if page * page_size >= total:
            break
        page += 1

    return calls


def to_calls_txt(calls: list[dict]) -> str:
    """Render calls in the same '---'-delimited format as calls.txt."""
    blocks = []
    for c in calls:
        lines = ["---"]
        for key in ("ID", "TÍTULO", "CLUSTER", "ESTADO", "DEADLINE", "BUDGET", "SCOPE"):
            lines.append(f"{key}: {c.get(key, '')}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks) + "\n"


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    calls = fetch_calls(status=("open", "forthcoming"), max_results=n)
    sys.stdout.write(to_calls_txt(calls))
    sys.stderr.write(f"\nFetched {len(calls)} Horizon Europe calls.\n")
