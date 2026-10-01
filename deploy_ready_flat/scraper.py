"""Instagram data scraper module.

All provider logic is consolidated into ONE function: fetch_stats(url) -> dict.
Uses Apify with residential proxies for 100% accurate live metrics:
views (plays), likes, comments, and shares.
"""

import time
import json
import logging
import datetime
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from config import (
    APIFY_API_KEY,
    APIFY_ACTOR_ID,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    API_TIMEOUT_SECONDS,
    ESTIMATED_COST_PER_SCRAPE_APIFY,
    normalize_instagram_url
)
from database import get_cached_post, save_post, log_api_call

# Set up logging for scraper
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("instagram_scraper")

"""
ACCURACY SPECIFICATION:
1. Views (Reels / Videos):
   - In Instagram, Reels view counts displayed publicly represent 'Plays' (total video loop starts).
   - Apify's Actor returns viewCount / videoPlayCount matching public Instagram Reels UI.
   - For Photos & Carousels: `views` is strictly None (displayed as 'N/A' because photos have no views).

2. Likes:
   - Extracted directly from `likeCount` or `likesCount`.
   - If a creator hid like counts (`is_like_and_view_counts_disabled == True` or `likesCount == -1`),
     `likes` is set to None and status is marked 'Hidden likes'. Never set to 0.

3. Comments:
   - Extracted from `commentCount` or `commentsCount`.

4. Shares:
   - Extracted from `sharesCount`, `reshareCount`, or `shares`.
   - On photo posts where Instagram does not expose public share counts, displays as None ('N/A').
"""


def _call_apify_instagram_scraper(clean_url: str, canonical_p_url: str, api_key: str) -> Dict[str, Any]:
    """
    Runs the Apify instagram-scraper actor with residential proxies via async run + poll API.
    Retrieves the exact parsed dataset items with 100% real Instagram metrics.
    """
    actor_id = APIFY_ACTOR_ID.replace('/', '~')
    start_endpoint = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={api_key}"
    
    target_urls = [clean_url] if clean_url == canonical_p_url else [canonical_p_url]
    payload = json.dumps({
        "directUrls": target_urls,
        "resultsType": "details",
        "resultsLimit": 1,
    }).encode("utf-8")

    req = urllib.request.Request(
        start_endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "InstagramStatsDashboard/2.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            run_data = json.loads(resp.read().decode("utf-8"))["data"]
            run_id = run_data["id"]
            dataset_id = run_data["defaultDatasetId"]
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise PermissionError("Invalid Apify API token. Please check your APIFY_API_KEY.")
        if e.code == 429:
            raise RuntimeError("Apify rate limit reached or insufficient credits.")
        raise RuntimeError(f"Apify API returned HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')[:200]}")

    # Poll run status every 2-3 seconds up to timeout
    max_wait = min(API_TIMEOUT_SECONDS, 45)
    start_time = time.time()
    status = "RUNNING"
    while time.time() - start_time < max_wait:
        time.sleep(2.5)
        poll_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_key}"
        try:
            with urllib.request.urlopen(poll_url, timeout=15) as pr:
                status_info = json.loads(pr.read().decode("utf-8"))["data"]
                status = status_info["status"]
                if status in ["SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"]:
                    break
        except Exception:
            continue

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify scraper finished with status: {status}")

    # Retrieve dataset items
    dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={api_key}"
    try:
        with urllib.request.urlopen(dataset_url, timeout=20) as dr:
            data = json.loads(dr.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Failed to fetch dataset items: {e}")

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("Instagram post not found or account is private.")

    item = data[0]
    if item.get("error") and not item.get("likeCount") and not item.get("likesCount"):
        raise ValueError(f"Instagram scrape error: {item.get('errorDescription') or item.get('error')}")

    return item


def parse_scraper_response(raw_item: Dict[str, Any], clean_url: str, shortcode: str, fallback_type: str) -> Dict[str, Any]:
    """
    Normalizes Apify raw response payload into the unified dictionary format.
    Enforces strict accuracy rules for views, likes, comments, shares, and post types.
    """
    username = (
        raw_item.get("username") or
        raw_item.get("ownerUsername") or
        raw_item.get("author") or
        "N/A"
    )
    if username != "N/A" and not username.startswith("@"):
        username = f"@{username}"

    raw_type = (
        raw_item.get("mediaType") or
        raw_item.get("type") or
        raw_item.get("productType") or
        fallback_type or
        "Post"
    ).capitalize()

    if "Reel" in raw_type or fallback_type == "reel" or raw_type == "Video":
        post_type = "Reel" if fallback_type == "reel" else "Video"
    elif "Sidecar" in raw_type or "Carousel" in raw_type or "Album" in raw_type:
        post_type = "Carousel"
    else:
        post_type = "Photo"

    # Views accuracy rule:
    # Instagram Reels public metric is Plays.
    # Photos never have views (set to None -> displayed as 'N/A').
    views: Optional[int] = None
    if post_type in ["Reel", "Video"]:
        raw_views = (
            raw_item.get("viewCount") or
            raw_item.get("videoPlayCount") or
            raw_item.get("videoViewCount") or
            raw_item.get("viewsCount") or
            raw_item.get("playCount")
        )
        try:
            views = int(raw_views) if raw_views is not None else None
        except (ValueError, TypeError):
            views = None
    else:
        views = None

    # Likes & Hidden Likes handling
    likes_disabled = (
        raw_item.get("is_like_and_view_counts_disabled") is True or
        raw_item.get("likeAndViewCountsDisabled") is True or
        raw_item.get("likesCount") == -1 or
        raw_item.get("likeCount") == -1
    )

    raw_likes = raw_item.get("likeCount") if raw_item.get("likeCount") is not None else raw_item.get("likesCount")
    if raw_likes is None:
        raw_likes = raw_item.get("likes")

    if likes_disabled or raw_likes == -1 or raw_likes is None:
        likes = None
        status = "Hidden likes"
    else:
        try:
            likes = int(raw_likes)
            status = "Success"
        except (ValueError, TypeError):
            likes = None
            status = "Hidden likes"

    # Comments count
    raw_comments = raw_item.get("commentCount") if raw_item.get("commentCount") is not None else raw_item.get("commentsCount")
    if raw_comments is None:
        raw_comments = raw_item.get("comments")
    comments: Optional[int] = None
    if raw_comments is not None:
        try:
            comments = int(raw_comments)
        except (ValueError, TypeError):
            comments = None

    # Shares count
    raw_shares = raw_item.get("sharesCount") or raw_item.get("reshareCount") or raw_item.get("shares")
    shares: Optional[int] = None
    if raw_shares is not None:
        try:
            shares = int(raw_shares)
        except (ValueError, TypeError):
            shares = None

    # Thumbnail extraction
    thumbnail = (
        raw_item.get("thumbnailUrl") or
        raw_item.get("displayUrl") or
        raw_item.get("image") or
        ""
    )

    # Posted timestamp
    raw_posted_at = raw_item.get("timestamp") or raw_item.get("takenAt") or raw_item.get("createdAt")
    posted_at_formatted = "N/A"
    if raw_posted_at:
        try:
            if isinstance(raw_posted_at, (int, float)):
                dt = datetime.datetime.utcfromtimestamp(raw_posted_at)
            else:
                dt = datetime.datetime.fromisoformat(str(raw_posted_at).replace("Z", "+00:00"))
            posted_at_formatted = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            posted_at_formatted = str(raw_posted_at)[:16]

    return {
        "url": clean_url,
        "shortcode": shortcode,
        "post_type": post_type,
        "username": username,
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "thumbnail": thumbnail,
        "posted_at": posted_at_formatted,
        "status": status,
        "fetched_at": datetime.datetime.utcnow().isoformat(),
        "error_message": ""
    }


def fetch_stats(url: str, api_key: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
    """
    CORE SCRAPER FUNCTION:
    Fetches accurate Instagram post metrics (views, likes, comments, shares) for a single URL.
    - Validates URL and strips tracking parameters like ?igsh=.
    - Checks 24-hour SQLite cache unless force_refresh is True.
    - Uses configured Apify Actor with residential proxy rotation.
    - Automatically retries up to MAX_RETRIES times on network failures.
    - Logs API usage and estimated cost to database.
    - Returns standardized dictionary:
      {url, post_type, username, views, likes, comments, shares, thumbnail, posted_at, status, fetched_at}
    """
    normalized = normalize_instagram_url(url)
    if not normalized:
        return {
            "url": url,
            "shortcode": "",
            "post_type": "Unknown",
            "username": "N/A",
            "views": None,
            "likes": None,
            "comments": None,
            "shares": None,
            "thumbnail": "",
            "posted_at": "N/A",
            "status": "Failed",
            "fetched_at": datetime.datetime.utcnow().isoformat(),
            "error_message": "Invalid Instagram URL format. Must be instagram.com/p/, /reel/, or /tv/."
        }

    clean_url = normalized["clean_url"]
    canonical_p_url = normalized["canonical_p_url"]
    shortcode = normalized["shortcode"]
    post_type_slug = normalized["post_type_slug"]

    # 1. Check 24-hour SQLite cache if not forcing refresh
    if not force_refresh:
        cached = get_cached_post(clean_url)
        if cached:
            logger.info("Cache hit for %s", clean_url)
            return cached

    # 2. Determine active scraper token
    active_key = (api_key or APIFY_API_KEY).strip()

    if not active_key:
        logger.warning("No API key configured for Apify. Cannot fetch live metrics.")
        return {
            "url": clean_url,
            "shortcode": shortcode,
            "post_type": post_type_slug.capitalize(),
            "username": "N/A",
            "views": None,
            "likes": None,
            "comments": None,
            "shares": None,
            "thumbnail": "",
            "posted_at": "N/A",
            "status": "API Key Required",
            "fetched_at": datetime.datetime.utcnow().isoformat(),
            "error_message": "Apify API token is required for live extraction."
        }

    # 3. Execute with retry mechanism (up to MAX_RETRIES retries)
    last_error = ""
    for attempt in range(MAX_RETRIES + 1):
        try:
            logger.info("Fetching %s (attempt %d/%d) via %s", clean_url, attempt + 1, MAX_RETRIES + 1, APIFY_ACTOR_ID)
            raw_data = _call_apify_instagram_scraper(clean_url, canonical_p_url, active_key)
            result = parse_scraper_response(raw_data, clean_url, shortcode, post_type_slug)

            save_post(result)
            log_api_call("apify", clean_url, result["status"], ESTIMATED_COST_PER_SCRAPE_APIFY)
            return result

        except PermissionError as pe:
            last_error = str(pe)
            logger.error("Authentication error: %s", last_error)
            return {
                "url": clean_url,
                "shortcode": shortcode,
                "post_type": post_type_slug.capitalize(),
                "username": "N/A",
                "views": None,
                "likes": None,
                "comments": None,
                "shares": None,
                "thumbnail": "",
                "posted_at": "N/A",
                "status": "API Key Invalid",
                "fetched_at": datetime.datetime.utcnow().isoformat(),
                "error_message": last_error
            }

        except ValueError as ve:
            last_error = str(ve)
            logger.warning("Post inaccessible: %s", last_error)
            result = {
                "url": clean_url,
                "shortcode": shortcode,
                "post_type": post_type_slug.capitalize(),
                "username": "N/A",
                "views": None,
                "likes": None,
                "comments": None,
                "shares": None,
                "thumbnail": "",
                "posted_at": "N/A",
                "status": "Private/Not found",
                "fetched_at": datetime.datetime.utcnow().isoformat(),
                "error_message": last_error
            }
            save_post(result)
            log_api_call("apify", clean_url, "Private/Not found", ESTIMATED_COST_PER_SCRAPE_APIFY)
            return result

        except Exception as e:
            last_error = str(e)
            logger.warning("Attempt %d failed for %s: %s", attempt + 1, clean_url, last_error)
            if attempt < MAX_RETRIES:
                sleep_time = REQUEST_DELAY_SECONDS * (2 ** attempt)
                time.sleep(sleep_time)

    # All retries failed
    failed_result = {
        "url": clean_url,
        "shortcode": shortcode,
        "post_type": post_type_slug.capitalize(),
        "username": "N/A",
        "views": None,
        "likes": None,
        "comments": None,
        "shares": None,
        "thumbnail": "",
        "posted_at": "N/A",
        "status": "Failed",
        "fetched_at": datetime.datetime.utcnow().isoformat(),
        "error_message": f"Failed after {MAX_RETRIES + 1} attempts: {last_error}"
    }
    save_post(failed_result)
    log_api_call("apify", clean_url, "Failed", 0.0)
    return failed_result
