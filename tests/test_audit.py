"""
Tests for app.audit — the framework-agnostic parsing/validation logic.

Run with: pytest

These mock the network layer (requests.get) so tests are fast and
deterministic — no real HTTP calls are made.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from app.audit import AuditError, build_report, fetch_page, validate_url


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------

def test_validate_url_adds_https_when_scheme_missing():
    assert validate_url("example.com") == "https://example.com"


def test_validate_url_accepts_valid_https():
    assert validate_url("https://example.com/page") == "https://example.com/page"


def test_validate_url_rejects_empty_string():
    with pytest.raises(AuditError) as exc_info:
        validate_url("")
    assert "required" in exc_info.value.message.lower()


def test_validate_url_rejects_non_http_scheme():
    # e.g. ftp:// — must not be silently rewritten, must be rejected
    with pytest.raises(AuditError) as exc_info:
        validate_url("ftp://example.com")
    assert "http" in exc_info.value.message.lower()


def test_validate_url_rejects_garbage_input():
    with pytest.raises(AuditError):
        validate_url("not a url at all")


# ---------------------------------------------------------------------------
# build_report — happy path
# ---------------------------------------------------------------------------

def test_build_report_happy_path():
    html = b"""
    <html>
    <head>
        <title>Example Page</title>
        <meta name="description" content="An example page for testing">
    </head>
    <body>
        <h1>Main Heading</h1>
        <img src="a.png" alt="a photo">
        <img src="b.png">
        <p>Some sample body copy for the word counter to tally up.</p>
    </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.url = "https://example.com/"
    mock_response.status_code = 200

    report = build_report("https://example.com", mock_response, html, 42.0)

    assert report["http_status"] == 200
    assert report["title"] == "Example Page"
    assert report["meta_description"] == "An example page for testing"
    assert report["h1_count"] == 1
    assert report["image_count"] == 2
    assert report["images_missing_alt"] == 1
    assert report["word_count"] == 13  # "Main Heading" + the 11-word paragraph
    assert report["response_time_ms"] == 42.0


def test_build_report_handles_missing_title_and_meta():
    html = b"<html><body><p>No head tags here.</p></body></html>"
    mock_response = MagicMock()
    mock_response.url = "https://example.com/"
    mock_response.status_code = 200

    report = build_report("https://example.com", mock_response, html, 10.0)

    assert report["title"] is None
    assert report["meta_description"] is None
    assert report["h1_count"] == 0


def test_build_report_word_count_excludes_head_and_scripts():
    html = b"""
    <html>
    <head><title>Ignored Title Words Here</title></head>
    <body>
        <script>var shouldNotCount = "these words too";</script>
        <p>Only these four words.</p>
    </body>
    </html>
    """
    mock_response = MagicMock()
    mock_response.url = "https://example.com/"
    mock_response.status_code = 200

    report = build_report("https://example.com", mock_response, html, 10.0)
    assert report["word_count"] == 4


# ---------------------------------------------------------------------------
# fetch_page — failure cases
# ---------------------------------------------------------------------------

def test_fetch_page_raises_on_timeout():
    with patch("app.audit.requests.get", side_effect=requests.exceptions.Timeout):
        with pytest.raises(AuditError) as exc_info:
            fetch_page("https://example.com")
    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.message.lower()


def test_fetch_page_raises_on_connection_error():
    with patch(
        "app.audit.requests.get", side_effect=requests.exceptions.ConnectionError
    ):
        with pytest.raises(AuditError) as exc_info:
            fetch_page("https://example.com")
    assert exc_info.value.status_code == 502


def test_fetch_page_rejects_non_html_content_type():
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.iter_content.return_value = [b'{"not": "html"}']

    with patch("app.audit.requests.get", return_value=mock_response):
        with pytest.raises(AuditError) as exc_info:
            fetch_page("https://example.com")
    assert exc_info.value.status_code == 415


def test_fetch_page_rejects_oversized_response():
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "text/html"}
    big_chunk = b"x" * (1024 * 1024)  # 1 MB per chunk
    mock_response.iter_content.return_value = [big_chunk] * 6  # 6 MB total

    with patch("app.audit.requests.get", return_value=mock_response):
        with pytest.raises(AuditError) as exc_info:
            fetch_page("https://example.com")
    assert exc_info.value.status_code == 413
