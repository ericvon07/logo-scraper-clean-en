"""Integration with the logo.dev REST API."""

import logging
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from logo_scraper.utils import (
    domain_from_url,
    get_image_dimensions,
    get_image_format,
    is_valid_image,
    sanitize_filename,
)

load_dotenv()

logger = logging.getLogger(__name__)

_BASE_URL = "https://img.logo.dev"


def build_logodev_url(domain, api_key, size=200, format="png"):
    return f"{_BASE_URL}/{domain}?token={api_key}&size={size}&format={format}"


def check_logodev_available(url):
    try:
        response = requests.head(url, timeout=10)
        return response.status_code == 200
    except requests.RequestException as exc:
        logger.debug("HEAD request failed for %s: %s", url, exc)
        return False


def fetch_logodev_candidates(company, domain, api_key):
    url = build_logodev_url(domain, api_key)
    logger.info("Checking logo.dev for %s: %s", domain, url)

    if check_logodev_available(url):
        logger.info("Logo available for %s", domain)
        return [
            {
                "company": company,
                "source": "logodev",
                "url": url,
                "local_path": None,
                "width": None,
                "height": None,
                "format": None,
            }
        ]

    logger.debug("No logo found for %s", domain)
    return []


def scrape_logodev(domain, output_dir, api_key=None):
    """Fetch and save logos from logo.dev for domain, trying common domain variants."""
    api_key = api_key or os.getenv("LOGODEV_API_KEY")
    if not api_key:
        raise ValueError(
            "logo.dev API key not found. "
            "Set LOGODEV_API_KEY in your environment or .env file."
        )

    # Normalise input to a bare domain
    if "://" in domain or "/" in domain:
        bare = domain_from_url(domain)
    elif "." not in domain:
        # Looks like a company name — try as-is then fall back to .com
        bare = domain
    else:
        bare = domain.removeprefix("www.")

    candidates = build_domain_variants(bare)
    company = bare.split(".")[0]

    output_dir.mkdir(parents=True, exist_ok=True)
    logos = []
    seen_domains = set()

    for candidate_domain in candidates:
        if candidate_domain in seen_domains:
            continue
        seen_domains.add(candidate_domain)

        logo_candidates = fetch_logodev_candidates(
            company=company, domain=candidate_domain, api_key=api_key
        )
        for logo in logo_candidates:
            filename = f"{sanitize_filename(company)}_logodev.png"
            dest = output_dir / filename

            try:
                response = requests.get(logo["url"], timeout=10, stream=True)
                response.raise_for_status()
                dest.write_bytes(response.content)

                if not is_valid_image(dest):
                    dest.unlink(missing_ok=True)
                    logger.warning(
                        "Downloaded content from %s is not a valid image", logo["url"]
                    )
                    continue

            except Exception as exc:
                logger.warning("Error downloading %s: %s", candidate_domain, exc)
                continue

            dims = get_image_dimensions(dest)
            fmt = get_image_format(dest)
            logo["local_path"] = dest
            logo["format"] = fmt
            if dims:
                logo["width"], logo["height"] = dims

            logos.append(logo)
            logger.info("Saved logo for %s -> %s (%s)", candidate_domain, dest, fmt)
            # One successful download is enough — stop trying variants
            return logos

    logger.info("No logos downloaded for %r", domain)
    return logos


def build_domain_variants(bare):
    variants = []

    if "." not in bare:
        # Company name only — try common TLDs
        variants.append(f"{bare}.com")
        return variants

    # Already a domain
    without_www = bare.removeprefix("www.")
    with_www = f"www.{without_www}"

    variants.append(without_www)
    variants.append(with_www)
    return variants
