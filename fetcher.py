"""Fetch and extract text from URLs with logging."""

from logger import get_logger

logger = get_logger("fetcher")


def fetch_text(url: str) -> str:
    """Fetch and extract text from a URL.

    Logs: URL fetched, text length, HTTP status, fallback used.
    """
    import httpx
    from bs4 import BeautifulSoup

    logger.debug(f"Fetching URL: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    # Try the URL as given; if an https connection fails (e.g. broken TLS),
    # fall back to http for the same host.
    candidates = [url]
    if url.startswith("https://"):
        candidates.append("http://" + url[len("https://"):])

    fallback_used = False
    for i, candidate in enumerate(candidates):
        try:
            logger.debug(f"Attempting: {candidate}")
            resp = httpx.get(
                candidate, timeout=15, follow_redirects=True, headers=headers
            )
            resp.raise_for_status()
            fallback_used = i > 0
            break
        except Exception as e:
            logger.debug(f"Failed: {candidate} - {str(e)}")
            continue
    else:
        logger.warning(f"Could not fetch {url} - all candidates failed")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()

    # Get visible text
    text = soup.get_text(separator=" ", strip=True)
    if text.strip():
        text = text[:6000]
        logger.info(f"Fetched {url} - {len(text)} chars, HTTP {resp.status_code}, fallback={fallback_used}")
        return text

    logger.warning(f"No text extracted from {url}")
    return ""
