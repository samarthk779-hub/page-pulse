"""
Core audit logic for Page Pulse.

Kept separate from Flask routing so it can be unit-tested without
spinning up the web server, and reused elsewhere if needed.
"""

import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT_SECONDS = 8
MAX_CONTENT_BYTES = 5 * 1024 * 1024  # 5 MB safety cap
USER_AGENT = "PagePulse/1.0 (+https://github.com/) audit bot"

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_WORD_RE = re.compile(r"\b[\w'-]+\b")


class AuditError(Exception):
    """Raised for any expected, user-facing audit failure.

    Carries an HTTP status code so the route layer can translate it
    directly into a response without re-deriving it.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def validate_url(raw_url: str) -> str:
    """Validate and normalize a URL, returning the normalized string.

    Raises AuditError with a user-facing message on anything invalid.
    """
    if not raw_url or not raw_url.strip():
        raise AuditError("URL is required.")

    raw_url = raw_url.strip()

    # Be forgiving: if someone pastes "example.com" (no scheme at all),
    # assume https. If they gave some other scheme (ftp://, mailto:, etc.)
    # leave it alone so it's rejected below with a clear message.
    if not _SCHEME_RE.match(raw_url):
        raw_url = "https://" + raw_url

    parsed = urlparse(raw_url)

    if parsed.scheme not in ("http", "https"):
        raise AuditError("URL must use http or https.")
    if not parsed.netloc:
        raise AuditError("That doesn't look like a valid URL.")

    hostname = parsed.hostname or ""
    if "." not in hostname and hostname != "localhost":
        raise AuditError("That doesn't look like a valid URL.")

    return raw_url


def fetch_page(url: str):
    """Fetch the page, enforcing timeouts, redirect limits, and size caps.

    Returns (response, content_bytes, elapsed_ms). Raises AuditError on
    any failure (timeout, connection error, wrong content type, etc.)
    """
    try:
        start = time.perf_counter()
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": USER_AGENT},
            stream=True,
            allow_redirects=True,
        )
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_CONTENT_BYTES:
                raise AuditError("Page is too large to audit (over 5 MB).", 413)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    except requests.exceptions.Timeout:
        raise AuditError(
            f"The request timed out after {REQUEST_TIMEOUT_SECONDS} seconds.", 504
        )
    except requests.exceptions.ConnectionError:
        raise AuditError("Could not connect to that URL. Check it's reachable.", 502)
    except requests.exceptions.TooManyRedirects:
        raise AuditError("Too many redirects.", 502)
    except requests.exceptions.RequestException as exc:
        raise AuditError(f"Failed to fetch the page: {exc}", 502)

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type.lower():
        raise AuditError(
            f"URL did not return HTML (Content-Type: {content_type or 'unknown'}).",
            415,
        )

    return response, content, elapsed_ms


def build_report(url: str, response, content: bytes, elapsed_ms: float) -> dict:
    """Parse fetched HTML into the audit report dict."""
    soup = BeautifulSoup(content, "html.parser")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    meta_desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = (
        meta_desc_tag.get("content", "").strip() if meta_desc_tag else None
    )

    h1_count = len(soup.find_all("h1"))

    images = soup.find_all("img")
    images_missing_alt = sum(1 for img in images if not img.get("alt", "").strip())

    # Approximate word count from visible body text only (excludes <head>,
    # <title>, scripts, and styles — those aren't "page content").
    body = soup.find("body") or soup
    for tag in body(["script", "style", "noscript"]):
        tag.decompose()
    text = body.get_text(separator=" ")
    word_count = len(_WORD_RE.findall(text))

    return {
        "url": url,
        "final_url": response.url,
        "http_status": response.status_code,
        "response_time_ms": elapsed_ms,
        "title": title,
        "meta_description": meta_description,
        "h1_count": h1_count,
        "image_count": len(images),
        "images_missing_alt": images_missing_alt,
        "word_count": word_count,
    }


def run_audit(raw_url: str) -> dict:
    """Full pipeline: validate -> fetch -> parse -> report."""
    url = validate_url(raw_url)
    response, content, elapsed_ms = fetch_page(url)
    return build_report(url, response, content, elapsed_ms)
