"""Tests for logo_scraper.scraper.logodev."""

import io
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests
from PIL import Image

from logo_scraper.scraper.logodev import scrape_logodev

FAKE_API_KEY = "test-key-abc123"


def _minimal_png():
    """Return raw bytes of a minimal valid PNG image."""
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _mock_head(status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    return resp


def _mock_get(content=b"", status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    return resp


def test_scrape_logodev_happy_path(tmp_path):
    """Logo found: file saved, metadata populated."""
    with (
        patch(
            "logo_scraper.scraper.logodev.requests.head", return_value=_mock_head(200)
        ),
        patch(
            "logo_scraper.scraper.logodev.requests.get",
            return_value=_mock_get(_minimal_png()),
        ),
    ):
        logos = scrape_logodev("stripe.com", tmp_path, api_key=FAKE_API_KEY)

    assert len(logos) == 1
    assert Path(logos[0]["local_path"]).exists()
    assert logos[0]["source"] == "logodev"
    assert logos[0]["format"] == "PNG"
    assert logos[0]["width"] == 10
    assert logos[0]["height"] == 10


def test_scrape_logodev_no_logo_returns_empty(tmp_path):
    with patch(
        "logo_scraper.scraper.logodev.requests.head", return_value=_mock_head(404)
    ):
        assert scrape_logodev("nonexistent.com", tmp_path, api_key=FAKE_API_KEY) == []


def test_scrape_logodev_missing_api_key_raises(tmp_path):
    key = os.environ.pop("LOGODEV_API_KEY", None)
    try:
        with pytest.raises(ValueError, match="API key"):
            scrape_logodev("stripe.com", tmp_path, api_key=None)
    finally:
        if key:
            os.environ["LOGODEV_API_KEY"] = key
