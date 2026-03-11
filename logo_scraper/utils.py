"""Utility functions: image download, validation, and helpers."""

import requests
from PIL import Image, UnidentifiedImageError


def download_image(url, dest, timeout=10):
    """Download an image from url and save it to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    dest.write_bytes(response.content)

    if not is_valid_image(dest):
        dest.unlink(missing_ok=True)
        raise ValueError(f"Downloaded content from {url!r} is not a valid image.")

    return dest


def is_valid_image(path):
    """Return True if path points to a readable image. SVG files are accepted by extension only."""
    if path.suffix.lower() == ".svg":
        return path.exists() and path.stat().st_size > 0

    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except (
        UnidentifiedImageError,
        Exception,
    ):  # not sure what other exceptions PIL can throw here
        return False


def get_image_dimensions(path):
    if path.suffix.lower() == ".svg":
        return None
    try:
        with Image.open(path) as img:
            return img.size  # (width, height)
    except Exception:
        return None


def get_image_format(path):
    if path.suffix.lower() == ".svg":
        return "SVG"
    try:
        with Image.open(path) as img:
            return img.format
    except Exception:
        return None


def sanitize_filename(name):
    unsafe = r'\/:*?"<>|'
    return "".join("_" if ch in unsafe else ch for ch in name)


def domain_from_url(url):
    from urllib.parse import urlparse

    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.netloc or parsed.path
    return host.removeprefix("www.")
