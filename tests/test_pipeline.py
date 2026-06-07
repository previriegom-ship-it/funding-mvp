"""Test suite for the funding MVP pipeline."""

import json
import time
import os
from pathlib import Path

import pytest
import requests

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from fetcher import fetch_text
from profiler import analyze_group
from sector_mapping import classify_sectors
from matcher import match, parse_calls


class TestFetcher:
    """Tests for the fetcher module."""

    def test_fetcher_ging(self):
        """Test fetching GING website."""
        url = "https://ging.github.io/"
        text = fetch_text(url)

        assert text, "Fetched text should not be empty"
        assert len(text) > 500, f"Fetched text should be > 500 chars, got {len(text)}"
        assert "Next Generation" in text or "internet" in text.lower(), \
            "Text should contain relevant GING content"


class TestProfiler:
    """Tests for the profiler module."""

    def test_profiler_schema(self):
        """Test that cached GING profile has correct schema."""
        cache_file = Path("profiles/cache/ging_github_io.json")
        assert cache_file.exists(), "GING cache file should exist"

        with open(cache_file, encoding="utf-8") as f:
            profile = json.load(f)

        # Check required fields (15 core fields)
        required_fields = [
            "name", "institution", "department", "research_lines",
            "technologies_developed", "technical_capabilities", "application_domains",
            "type_of_research", "maturity_level", "funding_history",
            "primary_keywords", "secondary_keywords", "interdisciplinary_topics",
            "extraction_confidence", "explanation"
        ]
        for field in required_fields:
            assert field in profile, f"Profile missing required field: {field}"

        # Check sector fields
        assert "primary_sector" in profile, "Profile should have primary_sector"
        assert "primary_sector_label" in profile, "Profile should have primary_sector_label"
        assert "secondary_sectors" in profile, "Profile should have secondary_sectors"

        # Check values
        assert profile["primary_sector"] == "DIGITAL_TECH", \
            f"GING should be DIGITAL_TECH, got {profile['primary_sector']}"
        assert profile["extraction_confidence"] > 0.5, \
            f"Confidence should be > 0.5, got {profile['extraction_confidence']}"

        # Check cache metadata
        assert "_cache_meta" in profile, "Profile should have _cache_meta"
        cache_meta = profile["_cache_meta"]
        assert "url" in cache_meta, "Cache meta should have url"
        assert "cached_at" in cache_meta, "Cache meta should have cached_at"
        assert "expires_at" in cache_meta, "Cache meta should have expires_at"
        assert "content_hash" in cache_meta, "Cache meta should have content_hash"


class TestSectorClassification:
    """Tests for sector classification."""

    def test_sector_classification_ging(self):
        """Test that GING is correctly classified as DIGITAL_TECH."""
        cache_file = Path("profiles/cache/ging_github_io.json")
        with open(cache_file, encoding="utf-8") as f:
            profile = json.load(f)

        assert profile["primary_sector"] == "DIGITAL_TECH", \
            "GING should be classified as DIGITAL_TECH"

    def test_sector_classification_biomedical(self):
        """Test classification of a hypothetical biomedical group."""
        hypothetical_profile = {
            "name": "Biomedical Research Lab",
            "primary_keywords": ["genomics", "drug discovery", "clinical research", "biomedical"],
            "secondary_keywords": ["health", "disease", "patient", "diagnosis"],
            "technologies_developed": ["medical imaging platform"],
            "technical_capabilities": ["genomic sequencing", "biomarker analysis"],
            "application_domains": ["healthcare", "pharmaceutical"],
            "research_lines": [
                {
                    "name": "Genomics",
                    "description": "Study of genetic variation",
                    "keywords": ["genomics", "genetics"]
                }
            ],
            "explanation": "Group focuses on biomedical research including drug discovery",
            "interdisciplinary_topics": [],
            "type_of_research": "applied",
            "maturity_level": "mid",
            "funding_history": {"has_funding_history": True, "funding_types": []},
            "extraction_confidence": 0.8
        }

        classification = classify_sectors(hypothetical_profile)
        assert classification["primary_sector"] == "HEALTH_BIOMEDICAL", \
            f"Biomedical profile should be HEALTH_BIOMEDICAL, got {classification['primary_sector']}"


class TestMatcher:
    """Tests for the matcher module."""

    def test_matcher_returns_results(self):
        """Test that matcher returns valid results."""
        # Load GING profile
        cache_file = Path("profiles/cache/ging_github_io.json")
        with open(cache_file, encoding="utf-8") as f:
            profile = json.load(f)

        # Match against calls
        results = match(profile, calls_path="calls_live.txt", top_n=10)

        assert len(results) >= 3, f"Should return at least 3 results, got {len(results)}"
        assert all(r["score"] > 0 for r in results), "All results should have score > 0"
        assert all("sector_match" in r for r in results), \
            "All results should have sector_match field"
        assert all(r["sector_match"] in ["primary", "secondary", "none"] for r in results), \
            "sector_match should be one of: primary, secondary, none"

        # Check sorting (highest score first)
        for i in range(len(results) - 1):
            assert results[i]["score"] >= results[i + 1]["score"], \
                "Results should be sorted by score descending"

    def test_matcher_call_filtering(self):
        """Test that matcher correctly filters calls."""
        calls = parse_calls("calls_live.txt")
        assert len(calls) > 0, "Should load some calls"

        # Check that open/upcoming calls are returned
        cache_file = Path("profiles/cache/ging_github_io.json")
        with open(cache_file, encoding="utf-8") as f:
            profile = json.load(f)

        results = match(profile, calls_path="calls_live.txt", top_n=100)
        # Results should not include "Cerrada" status
        assert all(r["estado"].lower() != "cerrada" for r in results), \
            "Results should not include closed (Cerrada) calls"


class TestCache:
    """Tests for caching functionality."""

    def test_cache_performance(self):
        """Test that cache significantly improves performance."""
        # Use GING which we know is cached
        test_url = "https://ging.github.io/"

        # First call with cache
        start = time.time()
        profile1 = analyze_group(test_url, force_refresh=False)
        time1 = time.time() - start

        # Should be cached and very fast
        assert time1 < 1.0, f"Cached call should be < 1s, took {time1:.2f}s"
        assert "error" not in profile1

        # Verify cache exists and has proper metadata
        cache_file = Path("profiles/cache/ging_github_io.json")
        assert cache_file.exists()

        print(f"\nCache performance: cached lookup={time1:.4f}s")

    def test_cache_expiration_field(self):
        """Test that cache has proper expiration tracking."""
        cache_file = Path("profiles/cache/ging_github_io.json")
        with open(cache_file, encoding="utf-8") as f:
            profile = json.load(f)

        cache_meta = profile.get("_cache_meta", {})
        expires_at = cache_meta.get("expires_at")

        assert expires_at, "Cache should have expires_at timestamp"

        # Parse expiration and verify it's in the future
        from datetime import datetime
        expires = datetime.fromisoformat(expires_at)
        assert expires > datetime.now(), "Cache should not be expired"


class TestIntegration:
    """Integration tests."""

    def test_full_pipeline(self):
        """Test the complete pipeline: fetch -> profile -> classify -> match."""
        # Start with fetching
        url = "https://ging.github.io/"
        text = fetch_text(url)
        assert len(text) > 500

        # Profile (using cache)
        profile = analyze_group(url)
        assert "error" not in profile
        assert profile["primary_sector"] == "DIGITAL_TECH"

        # Match
        results = match(profile, calls_path="calls_live.txt", top_n=5)
        assert len(results) > 0
        assert all("score" in r for r in results)
        assert all("sector_match" in r for r in results)

        print(f"\nFull pipeline test passed: {len(results)} opportunities found")


class TestData:
    """Tests for data files and structure."""

    def test_calls_file_exists(self):
        """Test that calls file exists and is readable."""
        calls = parse_calls("calls_live.txt")
        assert len(calls) > 0, "Should load calls from calls_live.txt"
        assert all("ID" in c for c in calls), "Each call should have ID"
        assert all("TÍTULO" in c for c in calls), "Each call should have TÍTULO"

    def test_profiles_directory(self):
        """Test that profile directories exist."""
        assert Path("profiles/cache").exists(), "profiles/cache should exist"
        assert Path("profiles/raw").exists(), "profiles/raw should exist"
        assert Path("profiles/archive").exists(), "profiles/archive should exist"

    def test_logs_directory(self):
        """Test that logs directory exists."""
        assert Path("logs").exists(), "logs directory should exist"
        # Note: app.log is created on first run


class TestAPI:
    """Tests for the API (requires running server)."""

    @pytest.mark.skip(reason="API tests require running server. Run with: uvicorn api:app --port 8000")
    def test_api_health(self):
        """Test API health endpoint."""
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
        except requests.ConnectionError:
            pytest.skip("API server not running")

    @pytest.mark.skip(reason="API tests require running server. Run with: uvicorn api:app --port 8000")
    def test_api_analyze(self):
        """Test API analyze endpoint."""
        try:
            payload = {"url": "https://ging.github.io/", "force_refresh": False}
            response = requests.post("http://localhost:8000/analyze", json=payload, timeout=30)
            assert response.status_code == 200
            data = response.json()
            assert "profile" in data
            assert "opportunities" in data
        except requests.ConnectionError:
            pytest.skip("API server not running")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
