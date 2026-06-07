"""FastAPI service for the funding matcher.

Run with:
    uvicorn api:app --reload --port 8000

Endpoints:
    POST /analyze  -> {profile, opportunities}
    GET  /health   -> {"status": "ok"}
"""

import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from profiler import analyze_group
from matcher import match
from logger import get_logger

logger = get_logger("api")

app = FastAPI(title="Funding Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    url: str
    force_refresh: bool = False
    top_n: int = 10         # size of the general top-N list
    detail_level: str = "full"  # "quick" | "sectors" | "full" | "all"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    start_time = time.time()
    url = (req.url or "").strip()

    logger.info(f"Analyze request received: {url} (force_refresh={req.force_refresh})")

    if not url:
        logger.warning("Analyze request: missing URL")
        raise HTTPException(status_code=400, detail="url is required")

    # Build the profile. analyze_group catches fetch/parse problems and
    # returns an {"error": ...} dict; anything else (e.g. an Anthropic API
    # failure) surfaces as an exception we convert to a 502.
    try:
        profile = analyze_group(url, force_refresh=req.force_refresh)
    except Exception as exc:
        logger.error(f"Profiling failed for {url}: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=502, detail="Profile generation failed. Check the URL and try again.")

    if isinstance(profile, dict) and "error" in profile:
        # Empty page / unfetchable URL / unparseable model output.
        logger.warning(f"Profile error for {url}: {profile['error']}")
        raise HTTPException(status_code=422, detail=profile["error"])

    try:
        results = match(profile, top_n=req.top_n, detail_level=req.detail_level)
    except Exception as exc:
        logger.error(f"Matching failed for {url}: {str(exc)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Opportunity matching failed. Please try again.")

    # "quick" returns a plain list (backward-compatible); everything else is
    # a structured dict that the frontend unpacks itself.
    if isinstance(results, list):
        opportunities = [
            {
                "id":           r["id"],
                "title":        r["title"],
                "status":       r["status"],
                "score":        r["score"],
                "deadline":     r["deadline"],
                "sector_match": r.get("sector_match", "none"),
                "call_sector":  r.get("call_sector", "UNKNOWN"),
            }
            for r in results
        ]
        top_count = len(opportunities)
    else:
        opportunities = results   # structured dict — frontend decides what to show
        top_count = len(results.get("top_10_general", []))

    elapsed = time.time() - start_time
    logger.info(
        f"Analyze request completed — {top_count} top opportunities "
        f"(detail_level={req.detail_level!r}) in {elapsed:.2f}s"
    )

    return {"profile": profile, "opportunities": opportunities}
