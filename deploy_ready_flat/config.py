"""Configuration settings and environment variable management."""

import os
import re
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

# Active Pre-configured Apify Scraper Token
APIFY_API_KEY: str = os.getenv("APIFY_API_KEY", "").strip()

SCRAPECREATORS_API_KEY: str = os.getenv("SCRAPECREATORS_API_KEY", "").strip()

# Primary Actor: apify/instagram-scraper (Official Apify scraper with residential proxy)
SCRAPER_PROVIDER: str = os.getenv("SCRAPER_PROVIDER", "scrapecreators").strip().lower()
APIFY_ACTOR_ID: str = os.getenv("APIFY_ACTOR_ID", "apify/instagram-scraper")

# Database Configuration (Built-in default, no key needed)
DB_PATH: str = os.getenv("DB_PATH", "instagram_stats.db")

# Cache settings: 24 hours before cache expires (Built-in default, no key needed)
CACHE_EXPIRY_HOURS: int = int(os.getenv("CACHE_EXPIRY_HOURS", "24"))

# Execution & Rate Limit parameters (Built-in defaults, no key needed)
MAX_RETRIES: int = 2
REQUEST_DELAY_SECONDS: float = float(os.getenv("REQUEST_DELAY_SECONDS", "1.2"))
API_TIMEOUT_SECONDS: int = int(os.getenv("API_TIMEOUT_SECONDS", "60"))

ESTIMATED_COST_PER_SCRAPE_APIFY: float = 0.003

# Instagram URL validation pattern
INSTAGRAM_URL_REGEX = re.compile(
    r"https?://(?:www\.)?instagram\.com/(p|reel|tv)/([A-Za-z0-9_-]+)/?",
    re.IGNORECASE
)


def normalize_instagram_url(url: str) -> Optional[dict]:
    """
    Validates and cleans an Instagram URL.
    Strips tracking query parameters (e.g., ?igsh=, ?utm_source=, ?img_index=).
    Returns a dict with 'clean_url', 'canonical_p_url', 'post_type_slug', and 'shortcode',
    or None if invalid.
    """
    if not url or not isinstance(url, str):
        return None

    stripped_url = url.strip()
    match = INSTAGRAM_URL_REGEX.search(stripped_url)
    if not match:
        return None

    post_type_slug = match.group(1).lower()  # 'p', 'reel', or 'tv'
    shortcode = match.group(2)
    clean_url = f"https://www.instagram.com/{post_type_slug}/{shortcode}/"
    canonical_p_url = f"https://www.instagram.com/p/{shortcode}/"

    return {
        "clean_url": clean_url,
        "canonical_p_url": canonical_p_url,
        "post_type_slug": post_type_slug,
        "shortcode": shortcode,
    }
