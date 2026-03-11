"""Tests for logo_scraper.cli."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from logo_scraper.cli import build_parser, main


def _make_result(company, domain, n_logos=1, source="logodev"):
    logos = [
        {
            "company": company,
            "source": source,
            "url": f"https://example.com/{i}.png",
            "local_path": None,
            "width": None,
            "height": None,
            "format": None,
        }
        for i in range(n_logos)
    ]
    return {"company": company, "domain": domain, "logos": logos, "errors": []}


def _write_json(tmp_path, data):
    f = tmp_path / "companies.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def test_parser_requires_name_or_from_file():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_single_mode_success_returns_0(capsys):
    with patch(
        "logo_scraper.cli.fetch_logos",
        return_value=_make_result("Nubank", "nubank.com"),
    ):
        assert main(["--name", "Nubank", "--url", "https://nubank.com"]) == 0


def test_batch_mode_success_returns_0(tmp_path, capsys):
    companies = [
        {"name": "Nubank", "url": "https://nubank.com", "linkedin": None},
        {"name": "Stripe", "url": "https://stripe.com", "linkedin": None},
    ]
    f = _write_json(tmp_path, companies)
    results = [
        _make_result("Nubank", "nubank.com"),
        _make_result("Stripe", "stripe.com"),
    ]
    with patch("logo_scraper.cli.fetch_logos", side_effect=results):
        assert main(["--from-file", str(f), "--output", str(tmp_path)]) == 0


def test_batch_mode_missing_file_returns_2(tmp_path, capsys):
    assert (
        main(["--from-file", str(tmp_path / "missing.json"), "--output", str(tmp_path)])
        == 2
    )
