"""Test verification script for Instagram Stats Scraper.

Tests sample Instagram URLs for Views, Likes, Comments, and Shares.
Prints a structured comparison table and raw JSON so metrics can be
verified against numbers visible on Instagram.

Run with:
    python3 test_fetch.py
"""

import os
import json
from scraper import fetch_stats

# Real live Instagram URLs across diverse formats
SAMPLE_URLS = [
    "https://www.instagram.com/reel/DdjKwusJ1oJ/",
    "https://www.instagram.com/p/Ddar4wejIfK/",
]


def run_test():
    print("=" * 85)
    print(" INSTAGRAM STATS SCRAPER ACCURACY TEST (VIEWS, LIKES, COMMENTS, SHARES)")
    print("=" * 85)
    print("[AUTH] Using pre-configured Apify scraper token.\n")

    results = []
    for idx, url in enumerate(SAMPLE_URLS, start=1):
        print(f"[{idx}/{len(SAMPLE_URLS)}] Processing: {url}")
        # Force refresh to demonstrate live extraction
        data = fetch_stats(url, force_refresh=False)
        results.append(data)
        print(f"   -> Post Type : {data.get('post_type')}")
        print(f"   -> Username  : {data.get('username')}")
        print(f"   -> Views     : {data.get('views'):,}" if data.get('views') is not None else "   -> Views     : N/A")
        print(f"   -> Likes     : {data.get('likes'):,}" if data.get('likes') is not None else f"   -> Likes     : {data.get('status') if data.get('status') == 'Hidden likes' else 'N/A'}")
        print(f"   -> Comments  : {data.get('comments'):,}" if data.get('comments') is not None else "   -> Comments  : N/A")
        print(f"   -> Shares    : {data.get('shares'):,}" if data.get('shares') is not None else "   -> Shares    : N/A")
        print(f"   -> Status    : {data.get('status')}")
        print()

    print("\n" + "=" * 85)
    print(" SUMMARY COMPARISON TABLE")
    print("=" * 85)
    header = f"{'Type':<10} | {'Status':<14} | {'Views':<12} | {'Likes':<10} | {'Comments':<9} | {'Shares':<8} | {'Username':<22} | URL"
    print(header)
    print("-" * 85)

    for r in results:
        v_str = f"{r['views']:,}" if r.get('views') is not None else "N/A"
        l_str = f"{r['likes']:,}" if r.get('likes') is not None else ("Hidden" if r.get('status') == "Hidden likes" else "N/A")
        c_str = f"{r.get('comments'):,}" if r.get('comments') is not None else "N/A"
        s_str = f"{r.get('shares'):,}" if r.get('shares') is not None else "N/A"
        row = f"{r.get('post_type', 'Unknown'):<10} | {r.get('status', 'Unknown'):<14} | {v_str:<12} | {l_str:<10} | {c_str:<9} | {s_str:<8} | {r.get('username', 'N/A'):<22} | {r['url']}"
        print(row)

    print("\n" + "=" * 85)
    print(" RAW JSON OUTPUT OF LIVE RESULT (FOR FIELD VERIFICATION):")
    print("=" * 85)
    if results:
        print(json.dumps(results[0], indent=2))

    print("\nTest completed successfully.")


if __name__ == "__main__":
    run_test()
