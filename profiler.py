import json
import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from logger import get_logger

load_dotenv(Path(__file__).parent / ".env")

logger = get_logger("profiler")


def url_to_filename(url: str) -> str:
    """Convert URL to filename: remove https://, replace . and / with _, lowercase."""
    name = url.replace("https://", "").replace("http://", "")
    name = name.replace(".", "_").replace("/", "_").lower()
    name = name.rstrip("_")
    return name


def compute_hash(text: str) -> str:
    """Compute SHA256 hash of text."""
    return hashlib.sha256(text.encode()).hexdigest()


def generate_profile(text: str) -> str:
    """Generate research group profile using Claude API with logging."""
    import os
    import anthropic

    logger.debug(f"Generating profile - input text: {len(text)} chars")

    api_key = os.getenv("ANTHROPIC_API_KEY")

    client = anthropic.Anthropic(api_key=api_key)

    system = (
        "You are a research-group profiling assistant. Given the text of a "
        "research group's website, extract an accurate profile as a single "
        "JSON object that works for ANY research group in any field.\n\n"
        "Use EXACTLY this schema and these keys:\n"
        "{\n"
        '  "name": string,                       // the research group\'s name\n'
        '  "institution": string,                // parent university/org\n'
        '  "department": string,                 // department or faculty\n'
        '  "research_lines": [                    // distinct lines of research\n'
        "    {\n"
        '      "name": string,\n'
        '      "description": string,\n'
        '      "keywords": [string]\n'
        "    }\n"
        "  ],\n"
        '  "technologies_developed": [string],   // concrete tools/platforms/systems built\n'
        '  "technical_capabilities": [string],   // methods/skills the group can apply\n'
        '  "application_domains": [string],       // sectors/domains the work applies to\n'
        '  "type_of_research": "hybrid" | "fundamental" | "applied",\n'
        '  "maturity_level": "senior" | "mid" | "junior",\n'
        '  "funding_history": {\n'
        '    "has_funding_history": boolean,\n'
        '    "funding_types": [string]           // e.g. "Horizon Europe", "national", "industry"\n'
        "  },\n"
        '  "primary_keywords": [string],          // core topics central to the group\n'
        '  "secondary_keywords": [string],        // adjacent/supporting topics\n'
        '  "interdisciplinary_topics": [string],  // cross-field connections\n'
        '  "extraction_confidence": float,        // 0-1, your confidence in this extraction\n'
        '  "explanation": string                  // brief rationale for the profile\n'
        "}\n\n"
        "Rules:\n"
        "- Include every key. If a value is unknown, use an empty string, "
        "empty array, or false as appropriate — never omit a key.\n"
        "- Base every field strictly on evidence in the provided text; do not "
        "invent institutions, technologies, or funding.\n"
        "- Infer type_of_research and maturity_level from cues in the text "
        "(publications, citations, seniority, applied vs. theoretical focus) "
        "and reflect any uncertainty in extraction_confidence.\n"
        "- Respond with ONLY the JSON object and nothing else."
    )

    logger.debug("Claude API call started")
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        system=system,
        messages=[
            {"role": "user", "content": text},
            {"role": "assistant", "content": "{"},
        ],
    )

    # Log token usage and cost estimate
    if hasattr(response, "usage"):
        input_tokens = getattr(response.usage, "input_tokens", 0)
        output_tokens = getattr(response.usage, "output_tokens", 0)
        total_tokens = input_tokens + output_tokens
        # Haiku pricing: ~$0.80 per 1M input tokens, ~$4 per 1M output tokens (approximate)
        cost = (input_tokens * 0.80 + output_tokens * 4) / 1_000_000
        logger.info(f"Claude API call finished - {total_tokens} tokens (~${cost:.4f})")
    else:
        logger.debug("Claude API call finished (token usage unavailable)")

    if hasattr(response, "content") and isinstance(response.content, list):
        body = "".join(block.text for block in response.content if hasattr(block, "text"))
    elif hasattr(response, "content"):
        body = str(response.content)
    else:
        body = str(response)
    return "{" + body


def load_cached_profile(filename: str) -> dict | None:
    """Load profile from cache if valid (not expired). Return None if not cached or expired."""
    cache_path = Path("profiles/cache") / f"{filename}.json"
    if not cache_path.exists():
        logger.debug(f"Cache miss for {filename} (file not found)")
        return None

    try:
        with open(cache_path, encoding="utf-8") as f:
            data = json.load(f)

        cache_meta = data.get("_cache_meta", {})
        expires_at = cache_meta.get("expires_at")

        if expires_at:
            expires = datetime.fromisoformat(expires_at)
            if datetime.now() < expires:
                logger.info(f"Cache hit for {filename} (expires {expires_at})")
                return data
            else:
                logger.debug(f"Cache expired for {filename} (expired {expires_at})")
        return None
    except Exception as e:
        logger.debug(f"Cache load error for {filename}: {str(e)}")
        return None


def save_profile_to_cache(filename: str, profile: dict, url: str, raw_text: str, model_used: str) -> None:
    """Save profile to cache with metadata. Archive old cache if exists."""
    now = datetime.now()
    expires = now + timedelta(days=30)

    cache_meta = {
        "url": url,
        "cached_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "version": "1.0",
        "model_used": model_used,
        "extraction_source": "web",
        "manually_invalidated": False,
        "fetch_status": "success",
        "text_length": len(raw_text),
        "content_hash": compute_hash(raw_text),
    }

    # Archive old cache if exists
    cache_path = Path("profiles/cache") / f"{filename}.json"
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                old_data = json.load(f)
            old_cached_at = old_data.get("_cache_meta", {}).get("cached_at", "unknown")
            archive_name = f"{filename}_{old_cached_at.replace(':', '-')}.json".replace(".", "_")
            archive_path = Path("profiles/archive") / archive_name
            cache_path.rename(archive_path)
        except Exception:
            pass

    # Save new cache
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    profile_with_meta = {**profile, "_cache_meta": cache_meta}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(profile_with_meta, f, indent=2, ensure_ascii=False)

    # Save raw text
    raw_path = Path("profiles/raw") / f"{filename}.txt"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(raw_text)


def analyze_group(url: str, force_refresh: bool = False) -> dict:
    """Analyze research group from URL with caching support.

    Args:
        url: URL of the research group website
        force_refresh: If True, ignore cache and fetch fresh profile

    Returns:
        Profile dict with _cache_meta and sector classification
    """
    from fetcher import fetch_text
    from sector_mapping import classify_sectors

    filename = url_to_filename(url)
    logger.info(f"Analyzing group: {url} (force_refresh={force_refresh})")

    # Check cache first
    if not force_refresh:
        cached = load_cached_profile(filename)
        if cached is not None:
            logger.debug(f"Returning cached profile for {url}")
            return cached

    logger.debug(f"No valid cache - fetching fresh profile for {url}")

    # Fetch and analyze
    text = fetch_text(url)
    if not text.strip():
        logger.warning(f"Could not fetch any text from {url}")
        return {"error": f"Could not fetch any text from {url}"}

    profile_text = generate_profile(text)

    try:
        profile = json.loads(profile_text)
        logger.debug(f"Profile parsed successfully for {url}")
    except Exception as e:
        logger.error(f"Could not parse profile for {url}: {str(e)}")
        profile = {"error": "Could not parse profile", "raw": profile_text}
        return profile

    # Classify sectors
    sector_classification = classify_sectors(profile)
    profile.update(sector_classification)
    logger.debug(f"Sector classified as {profile.get('primary_sector')} for {url}")

    # Save to cache
    save_profile_to_cache(filename, profile, url, text, "claude-haiku-4-5-20251001")
    logger.debug(f"Profile cached for {url}")

    return profile
