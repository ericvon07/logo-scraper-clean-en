"""Extract logos directly from a company's website HTML."""

import logging
import mimetypes
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from logo_scraper.utils import (
    domain_from_url,
    download_image,
    get_image_dimensions,
    get_image_format,
    sanitize_filename,
)

logger = logging.getLogger(__name__)

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

_FAVICON_RELS = {"icon", "shortcut icon", "apple-touch-icon"}


def get_website_html(url, timeout=10):
    response = requests.get(url, timeout=timeout, headers=_BROWSER_HEADERS, verify=True)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def make_absolute(href, base_url):
    return urljoin(base_url, href)


def extract_favicons(soup, base_url):
    urls = []
    for tag in soup.find_all("link", rel=True):
        rels = {r.lower() for r in tag.get("rel", [])}
        if rels & _FAVICON_RELS:
            href = tag.get("href", "").strip()
            if href:
                urls.append(make_absolute(href, base_url))
    return urls


def extract_og_image(soup):
    urls = []
    for tag in soup.find_all("meta"):
        prop = tag.get("property", "") or tag.get("name", "")
        if prop.lower() in {"og:image", "og:image:url"}:
            content = tag.get("content", "").strip()
            if content:
                urls.append(content)
    return urls


def extract_twitter_image(soup):
    urls = []
    for tag in soup.find_all("meta", attrs={"name": True}):
        if tag["name"].lower() == "twitter:image":
            content = tag.get("content", "").strip()
            if content:
                urls.append(content)
    return urls


def extract_logo_imgs(soup, base_url):
    # TODO: this misses logos loaded via JavaScript
    urls = []
    for tag in soup.find_all("img"):
        src = tag.get("src", "").strip()
        alt = tag.get("alt", "").lower()
        if not src:
            continue
        if "logo" in src.lower() or "logo" in alt:
            urls.append(make_absolute(src, base_url))
    return urls


def fetch_website_logo_candidates(company, url, timeout=10):
    logger.info("Fetching logos from %s", url)
    try:
        soup = get_website_html(url, timeout=timeout)
    except requests.RequestException as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return []

    seen = set()
    logos = []

    candidate_urls = (
        extract_favicons(soup, url)
        + extract_og_image(soup)
        + extract_twitter_image(soup)
        + extract_logo_imgs(soup, url)
    )

    for img_url in candidate_urls:
        if img_url in seen:
            continue
        seen.add(img_url)
        logos.append(
            {
                "company": company,
                "source": "website",
                "url": img_url,
                "local_path": None,
                "width": None,
                "height": None,
                "format": None,
            }
        )
        logger.debug("Found candidate: %s", img_url)

    logger.info("Found %d logo candidate(s) on %s", len(logos), url)
    return logos


def scrape_website_logos(url, output_dir):
    """Scrape, download, and validate logos from url, saving them to output_dir."""
    domain = domain_from_url(url)
    company = domain.split(".")[0]
    candidates = fetch_website_logo_candidates(company=company, url=url)

    output_dir.mkdir(parents=True, exist_ok=True)
    logos = []

    for idx, logo in enumerate(candidates):
        filename = build_filename(logo["url"], company, idx)
        dest = output_dir / filename

        try:
            download_image(logo["url"], dest)
        except ValueError as exc:
            # download_image raises ValueError when Pillow rejects the file
            logger.warning("Invalid image at %s: %s", logo["url"], exc)
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
        logger.info("Saved %s -> %s (%s)", logo["url"], dest, fmt)

    logger.info("Downloaded %d/%d logo(s) from %s", len(logos), len(candidates), url)
    return logos


def build_filename(img_url, company, idx):
    parsed_path = urlparse(img_url).path
    ext = Path(parsed_path).suffix.lower()

    # Fall back to guessing extension from MIME type if URL has none
    if not ext or len(ext) > 5:
        guessed, _ = mimetypes.guess_type(img_url)
        ext = mimetypes.guess_extension(guessed or "") or ".png"

    safe_company = sanitize_filename(company)
    return f"{safe_company}_logo_{idx}{ext}"
