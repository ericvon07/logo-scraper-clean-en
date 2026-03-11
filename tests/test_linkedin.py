"""Tests for logo_scraper.scraper.linkedin.

All network calls are mocked — no real HTTP requests are made.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from logo_scraper.scraper.linkedin import (
    fetch_linkedin_logo_candidates,
    get_linkedin_html,
    scrape_linkedin_logo,
    walk_json,
)

_URL = "https://www.linkedin.com/company/stripe"

_HTML_OG_IMAGE = """\
<!DOCTYPE html>
<html><head>
  <meta property="og:image" content="https://media.licdn.com/dms/image/stripe-logo.png"/>
</head><body></body></html>
"""


def _make_response(status_code=200, text="", url=_URL):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = url
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def test_get_linkedin_html_success():
    with (
        patch("logo_scraper.scraper.linkedin.time.sleep"),
        patch(
            "logo_scraper.scraper.linkedin.requests.get",
            return_value=_make_response(text="<html><body>ok</body></html>"),
        ),
    ):
        soup = get_linkedin_html(_URL)
    assert soup is not None
    assert soup.find("body") is not None


def test_get_linkedin_html_blocked_returns_none():
    """403 or authwall redirect → None (not an exception)."""
    with (
        patch("logo_scraper.scraper.linkedin.time.sleep"),
        patch(
            "logo_scraper.scraper.linkedin.requests.get",
            return_value=_make_response(status_code=403),
        ),
    ):
        assert get_linkedin_html(_URL) is None


def test_fetch_candidates_happy_path():
    """og:image found → candidate returned with correct shape."""
    with (
        patch("logo_scraper.scraper.linkedin.time.sleep"),
        patch(
            "logo_scraper.scraper.linkedin.requests.get",
            return_value=_make_response(text=_HTML_OG_IMAGE),
        ),
    ):
        logos = fetch_linkedin_logo_candidates("Stripe", _URL)

    assert len(logos) == 1
    assert logos[0]["source"] == "linkedin"
    assert logos[0]["company"] == "Stripe"
    assert "stripe-logo.png" in logos[0]["url"]


def test_scrape_linkedin_logo_no_candidates_returns_empty(tmp_path):
    with patch(
        "logo_scraper.scraper.linkedin.fetch_linkedin_logo_candidates", return_value=[]
    ):
        assert scrape_linkedin_logo(_URL, tmp_path) == []
        assert list(tmp_path.iterdir()) == []


def test_walk_json_finds_logo_and_nested_url():
    data = {
        "logo": "https://example.com/logo.png",
        "nested": {"image": "https://example.com/img.png"},
    }
    results = walk_json(data)
    assert "https://example.com/logo.png" in results
    assert "https://example.com/img.png" in results
