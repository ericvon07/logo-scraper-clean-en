"""Tests for logo_scraper.scraper.website."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from bs4 import BeautifulSoup

from logo_scraper.scraper.website import (
    extract_favicons,
    fetch_website_logo_candidates,
    scrape_website_logos,
)

BASE_URL = "https://www.example.com"

COMBINED_HTML = """
<html><head>
  <link rel="icon" href="/favicon.ico">
  <meta property="og:image" content="https://cdn.example.com/og.png">
  <meta name="twitter:image" content="https://cdn.example.com/tw.png">
</head><body>
  <img src="/img/logo.png" alt="Acme logo">
</body></html>
"""


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def _mock_response(html, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            response=resp, request=MagicMock()
        )
    return resp


def test_extract_favicons_finds_icons():
    html = """<html><head>
      <link rel="icon" href="/favicon.ico">
      <link rel="apple-touch-icon" href="/apple.png">
      <link rel="stylesheet" href="/style.css">
    </head></html>"""
    urls = extract_favicons(_soup(html), BASE_URL)
    assert "https://www.example.com/favicon.ico" in urls
    assert "https://www.example.com/apple.png" in urls
    assert not any("style.css" in u for u in urls)


def test_fetch_candidates_finds_all_sources():
    """Combined page: favicon + og:image + twitter + img logo all returned."""
    with patch(
        "logo_scraper.scraper.website.requests.get",
        return_value=_mock_response(COMBINED_HTML),
    ):
        logos = fetch_website_logo_candidates("example", BASE_URL)

    assert len(logos) == 4
    assert all(lg["source"] == "website" for lg in logos)
    assert all(lg["local_path"] is None for lg in logos)


def test_scrape_website_logos_happy_path(tmp_path):
    """Logo downloaded: metadata populated."""
    logo = {
        "company": "example",
        "source": "website",
        "url": "https://cdn.example.com/logo.png",
        "local_path": None,
        "width": None,
        "height": None,
        "format": None,
    }
    with (
        patch(
            "logo_scraper.scraper.website.fetch_website_logo_candidates",
            return_value=[logo],
        ),
        patch(
            "logo_scraper.scraper.website.download_image",
            return_value=tmp_path / "logo.png",
        ),
        patch(
            "logo_scraper.scraper.website.get_image_dimensions", return_value=(200, 80)
        ),
        patch("logo_scraper.scraper.website.get_image_format", return_value="PNG"),
    ):
        result = scrape_website_logos("https://example.com", tmp_path)

    assert len(result) == 1
    assert result[0]["width"] == 200
    assert result[0]["format"] == "PNG"
