"""Extract company logos from LinkedIn company pages.

WARNING: This is the least reliable source in the scraper
LinkedIn aggressively blocks scraping
Success rate is low and can vary without notice
For production use, we should consider the LinkedIn Marketing API or using another source.
"""

import json
import logging
import mimetypes
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logo_scraper.utils import (
    domain_from_url,
    get_image_dimensions,
    get_image_format,
    is_valid_image,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

# Realistic browser headers to reduce the chance of immediate blocking.
# LinkedIn may still redirect to login or return 403.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Delay before each request (reduces rate limiting risk)
# TODO: maybe make this configurable?
_REQUEST_DELAY_SECONDS = 1.5

# HTTP status codes that indicate LinkedIn is blocking the request
_BLOCKED_STATUS_CODES = {403, 999}


def get_linkedin_html(url, timeout=15):
    time.sleep(_REQUEST_DELAY_SECONDS)

    response = requests.get(
        url,
        timeout=timeout,
        headers=_BROWSER_HEADERS,
        verify=True,
        allow_redirects=True,
    )

    if response.status_code in _BLOCKED_STATUS_CODES:
        logger.warning(
            "LinkedIn blocked the request for %s (HTTP %s). "
            "This is expected — returning empty list.",
            url,
            response.status_code,
        )
        return None

    final_url = response.url
    if "linkedin.com/authwall" in final_url or "linkedin.com/login" in final_url:
        logger.warning(
            "LinkedIn redirected to login for %s (%s). "
            "This is expected — returning empty list.",
            url,
            final_url,
        )
        return None

    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_og_image(soup):
    urls = []
    for tag in soup.find_all("meta"):
        prop = tag.get("property", "") or tag.get("name", "")
        if prop.lower() in {"og:image", "og:image:url"}:
            content = tag.get("content", "").strip()
            if content:
                urls.append(content)
    return urls


def extract_json_ld_images(soup):
    urls = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        for candidate in walk_json(data):
            if isinstance(candidate, str) and candidate.startswith("http"):
                urls.append(candidate)

    return urls


def extract_logo_imgs(soup, base_url):
    urls = []
    for tag in soup.find_all("img"):
        src = tag.get("src", "").strip()
        if not src:
            continue
        classes = " ".join(tag.get("class", []))
        alt = tag.get("alt", "").lower()
        if "logo" in src.lower() or "logo" in classes.lower() or "logo" in alt:
            urls.append(urljoin(base_url, src))
    return urls


def fetch_linkedin_logo_candidates(company, linkedin_url, timeout=15):
    logger.info("Fetching LinkedIn page: %s", linkedin_url)

    try:
        soup = get_linkedin_html(linkedin_url, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Network error fetching %s: %s", linkedin_url, exc)
        return []

    if soup is None:
        return []

    seen = set()
    logos = []

    candidate_urls = (
        extract_og_image(soup)
        + extract_json_ld_images(soup)
        + extract_logo_imgs(soup, linkedin_url)
    )

    for img_url in candidate_urls:
        if img_url in seen:
            continue
        seen.add(img_url)
        logos.append(
            {
                "company": company,
                "source": "linkedin",
                "url": img_url,
                "local_path": None,
                "width": None,
                "height": None,
                "format": None,
            }
        )
        logger.debug("LinkedIn logo candidate: %s", img_url)

    logger.info(
        "Found %d logo candidate(s) on LinkedIn for %s", len(logos), linkedin_url
    )
    return logos


def scrape_linkedin_logo(linkedin_url, output_dir):
    """Scrape, download, and validate logos from a LinkedIn company page.

    NOTE: This is the least reliable source — LinkedIn aggressively blocks scraping.
    If blocked, returns an empty list without raising an exception.
    """
    parsed = urlparse(linkedin_url)
    # Derive a company slug from the URL path: /company/stripe -> "stripe"
    path_parts = [p for p in parsed.path.split("/") if p]
    company = (
        path_parts[-1] if path_parts else domain_from_url(linkedin_url).split(".")[0]
    )

    candidates = fetch_linkedin_logo_candidates(
        company=company, linkedin_url=linkedin_url
    )

    if not candidates:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    logos = []

    for idx, logo in enumerate(candidates):
        filename = build_filename(logo["url"], company, idx)
        dest = output_dir / filename

        try:
            response = requests.get(logo["url"], timeout=10, stream=True)
            response.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(response.content)

            if not is_valid_image(dest):
                dest.unlink(missing_ok=True)
                logger.warning("Invalid image content at %s — skipping", logo["url"])
                continue

        except Exception as exc:
            logger.warning("Error downloading %s: %s", logo["url"], exc)
            continue

        dims = get_image_dimensions(dest)
        fmt = get_image_format(dest)
        logo["local_path"] = dest
        logo["format"] = fmt
        if dims:
            logo["width"], logo["height"] = dims

        logos.append(logo)
        logger.info("Saved LinkedIn logo -> %s (%s)", dest, fmt)

    logger.info(
        "Downloaded %d/%d LinkedIn logo(s) from %s",
        len(logos),
        len(candidates),
        linkedin_url,
    )
    return logos


def build_filename(img_url, company, idx):
    parsed_path = urlparse(img_url).path
    ext = Path(parsed_path).suffix.lower()
    if not ext or len(ext) > 5:
        guessed, _ = mimetypes.guess_type(img_url)
        ext = mimetypes.guess_extension(guessed or "") or ".png"
    safe_company = sanitize_filename(company)
    return f"{safe_company}_linkedin_{idx}{ext}"


def walk_json(obj):
    results = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key.lower() in {"logo", "image", "url"} and isinstance(value, str):
                results.append(value)
            else:
                results.extend(walk_json(value))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(walk_json(item))
    return results
