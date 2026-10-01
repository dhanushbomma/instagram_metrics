"""Instagram Stats Dashboard - Streamlit Web Application.

A production-ready dashboard to track, analyze, cache, and export Instagram
post and reel metrics (views, likes, comments, shares) with 100% accuracy.
"""

import time
import datetime
import pandas as pd
import streamlit as st

from config import (
    APIFY_API_KEY,
    SCRAPECREATORS_API_KEY,
    SCRAPER_PROVIDER,
    normalize_instagram_url
)
from database import (
    init_db,
    get_all_posts,
    get_api_usage_stats,
    clear_all_posts
)
from scraper import fetch_stats
from report import generate_excel_report, generate_pdf_report

# Page configuration
st.set_page_config(
    page_title="Instagram Stats Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ---------------- PASSWORD GATE (protects your API credits when public) ----------------
def _check_password() -> bool:
    import os
    try:
        expected = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        expected = ""
    expected = expected or os.getenv("APP_PASSWORD", "")
    if not expected:          # no password set -> open (fine for local use)
        return True
    if st.session_state.get("auth_ok"):
        return True
    st.title("🔒 Instagram Stats Dashboard")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if pwd == expected:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Wrong password")
    return False


if not _check_password():
    st.stop()

# Custom CSS for dashboard aesthetic
st.markdown("""
<style>
    .metric-card {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 0.8rem;
        color: #64748b;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0f172a;
        margin-top: 3px;
    }
</style>
""", unsafe_allow_html=True)


def parse_raw_inputs(text_input: str, uploaded_csv) -> list[str]:
    """Extracts, cleans, and deduplicates Instagram URLs from text and uploaded CSV."""
    urls = []

    if text_input:
        for line in text_input.strip().splitlines():
            clean = line.strip()
            if clean:
                urls.append(clean)

    if uploaded_csv is not None:
        try:
            df = pd.read_csv(uploaded_csv)
            url_col = None
            for col in df.columns:
                if any(k in str(col).lower() for k in ["url", "link", "instagram", "post", "reel"]):
                    url_col = col
                    break
            if url_col is None and len(df.columns) > 0:
                url_col = df.columns[0]

            if url_col:
                for val in df[url_col].dropna():
                    val_str = str(val).strip()
                    if val_str:
                        urls.append(val_str)
        except Exception as e:
            st.sidebar.error(f"Error reading CSV: {e}")

    valid_urls = []
    seen = set()
    for raw in urls:
        norm = normalize_instagram_url(raw)
        if norm and norm["clean_url"] not in seen:
            seen.add(norm["clean_url"])
            valid_urls.append(norm["clean_url"])

    return valid_urls


def calculate_metrics(posts: list[dict]) -> dict:
    """Calculates summary KPIs across all loaded posts including views, likes, comments, and shares."""
    total_posts = len(posts)
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    reels_count = 0

    for p in posts:
        if p.get("views") is not None and isinstance(p["views"], (int, float)):
            total_views += int(p["views"])
            reels_count += 1

        if p.get("likes") is not None and isinstance(p["likes"], (int, float)):
            total_likes += int(p["likes"])

        if p.get("comments") is not None and isinstance(p["comments"], (int, float)):
            total_comments += int(p["comments"])

        if p.get("shares") is not None and isinstance(p["shares"], (int, float)):
            total_shares += int(p["shares"])

    return {
        "total_posts": total_posts,
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "reels_count": reels_count,
        "avg_views_per_reel": int(total_views / reels_count) if reels_count > 0 else 0
    }


def main():
    init_db()

    # ---------------- SIDEBAR ----------------
    with st.sidebar:
        st.title("⚙️ Engine Settings")

        # Provider selection
        provider = st.selectbox(
            "Scraper Provider:",
            options=["apify", "scrapecreators"],
            index=0 if SCRAPER_PROVIDER == "apify" else 1,
            help="Apify uses the official 'apify/instagram-scraper' Actor with residential proxies."
        )

        # Allow user to paste API key right in the UI if not in .env
        default_key = APIFY_API_KEY if provider == "apify" else SCRAPECREATORS_API_KEY
        user_api_key = st.text_input(
            f"{provider.capitalize()} API Token:",
            value=st.session_state.get("custom_api_key", default_key),
            type="password",
            help="Get your free Apify token ($5 monthly recurring free credit) at https://console.apify.com/account/integrations"
        )
        if user_api_key:
            st.session_state["custom_api_key"] = user_api_key.strip()

        if user_api_key.strip():
            st.success("✅ API Key active for live extraction")
        else:
            st.error("⚠️ No API Key set.")
            st.markdown(
                """
                <small style="color: #94a3b8;">
                Instagram prevents unauthenticated scrapers from accessing post metrics.
                To extract <b>real views, likes, comments, and shares</b>, enter an
                <a href="https://console.apify.com/account/integrations" target="_blank" style="color: #6366f1;">Apify API Token</a>
                (Free tier includes $5/mo, good for ~1,500 scrapes).
                </small>
                """,
                unsafe_allow_html=True
            )

        st.divider()

        # API Usage and Cost Tracking
        st.subheader("💳 API Usage & Cost")
        usage_stats = get_api_usage_stats()
        c1, c2 = st.columns(2)
        c1.metric("Today's Calls", usage_stats["today_calls"])
        c2.metric("Today's Cost", f"${usage_stats['today_cost']:.3f}")
        st.caption(f"Lifetime Calls: {usage_stats['total_calls']} (${usage_stats['total_cost']:.2f})")

        st.divider()

        # Database / Cache Maintenance
        st.subheader("🗄️ Cache Settings")
        st.info("Results are stored in SQLite and cached for 24 hours to prevent redundant API charges.")
        if st.button("Clear SQLite Cache", type="secondary"):
            clear_all_posts()
            st.toast("Database cache cleared successfully!")
            st.rerun()

    # ---------------- MAIN HEADER ----------------
    st.title("📸 Instagram Stats Dashboard")
    st.caption("Live, accurate extraction of Views (Plays), Likes, Comments, and Shares for Instagram posts and reels.")

    # Show warning if no key is supplied
    effective_key = st.session_state.get("custom_api_key", default_key).strip()
    if not effective_key:
        st.warning(
            "🔑 **Apify API Key Required for Real Counts**: To extract real, accurate numbers from Instagram, "
            "please enter your Apify API Token in the sidebar on the left. (Get a free key with $5 credit at [apify.com](https://console.apify.com/account/integrations))."
        )

    # ---------------- URL INPUT SECTION ----------------
    with st.expander("📥 Add Instagram URLs (Paste or CSV Upload)", expanded=True):
        col_in1, col_in2 = st.columns([2, 1])

        with col_in1:
            urls_text = st.text_area(
                "Paste Instagram URLs (one per line):",
                placeholder="https://www.instagram.com/reel/C3bA1x4L_9y/\nhttps://www.instagram.com/p/C0xP99-rzQv/?igsh=...",
                height=130
            )

        with col_in2:
            uploaded_file = st.file_uploader(
                "Or upload a CSV file:",
                type=["csv"],
                help="Upload a CSV with a column containing Instagram URLs."
            )
            force_refresh = st.checkbox("Force refresh (bypass 24h cache)", value=False)

        parsed_urls = parse_raw_inputs(urls_text, uploaded_file)
        if parsed_urls:
            st.caption(f"✅ Found **{len(parsed_urls)}** valid, deduplicated Instagram URLs ready to process.")

        start_btn = st.button("🚀 Fetch Accurate Metrics", type="primary", disabled=(len(parsed_urls) == 0))

    # ---------------- SCRAPING EXECUTION PIPELINE ----------------
    if start_btn and parsed_urls:
        progress_bar = st.progress(0)
        status_box = st.empty()

        total = len(parsed_urls)
        for idx, url in enumerate(parsed_urls, start=1):
            status_box.markdown(f"**Fetching live data {idx}/{total}:** `{url}`...")
            fetch_stats(url, api_key=effective_key, force_refresh=force_refresh)
            progress_bar.progress(idx / total)
            time.sleep(0.1)

        progress_bar.empty()
        status_box.success(f"🎉 Completed processing {total} URLs!")
        time.sleep(0.5)
        st.rerun()

    # ---------------- LOAD SAVED POSTS FROM SQLITE ----------------
    posts = get_all_posts()

    # ---------------- KPI CARDS ----------------
    if posts:
        kpis = calculate_metrics(posts)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Total Posts</div>
                    <div class="metric-value">{kpis['total_posts']}</div>
                </div>
            """, unsafe_allow_html=True)
        with k2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label" style="color:#6366f1;">Total Views</div>
                    <div class="metric-value" style="color:#4f46e5;">{kpis['total_views']:,}</div>
                </div>
            """, unsafe_allow_html=True)
        with k3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label" style="color:#ec4899;">Total Likes</div>
                    <div class="metric-value" style="color:#db2777;">{kpis['total_likes']:,}</div>
                </div>
            """, unsafe_allow_html=True)
        with k4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label" style="color:#f59e0b;">Total Comments</div>
                    <div class="metric-value" style="color:#d97706;">{kpis['total_comments']:,}</div>
                </div>
            """, unsafe_allow_html=True)
        with k5:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label" style="color:#10b981;">Total Shares</div>
                    <div class="metric-value" style="color:#059669;">{kpis['total_shares']:,}</div>
                </div>
            """, unsafe_allow_html=True)
        with k6:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label" style="color:#8b5cf6;">Avg / Reel</div>
                    <div class="metric-value" style="color:#7c3aed;">{kpis['avg_views_per_reel']:,}</div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

    # ---------------- FAILED / MISSING KEY ACTION BANNER ----------------
    problem_posts = [p for p in posts if p.get("status") in ["Failed", "Private/Not found", "API Key Required", "API Key Invalid"]]
    if problem_posts:
        st.warning(f"⚠️ There are **{len(problem_posts)}** posts that failed or require attention.")
        if st.button(f"🔄 Retry {len(problem_posts)} Unresolved URLs", type="secondary"):
            retry_prog = st.progress(0)
            retry_box = st.empty()
            for r_idx, f_post in enumerate(problem_posts, start=1):
                retry_box.markdown(f"Retrying `{f_post['url']}`...")
                fetch_stats(f_post["url"], api_key=effective_key, force_refresh=True)
                retry_prog.progress(r_idx / len(problem_posts))
            retry_prog.empty()
            retry_box.empty()
            st.toast("Retry completed!")
            st.rerun()

    # ---------------- DATA TABLE & FILTERS ----------------
    st.subheader("📋 Tracked Posts Overview")

    if not posts:
        st.info("No Instagram posts tracked yet. Add URLs in the panel above to begin.")

    # ---------------- EXPORT SECTION ----------------
    st.divider()
    st.subheader("📥 Professional Report Section")
    st.write("Generate client-ready performance reports with an executive summary, KPI snapshot, top-performing content, and detailed post-level records.")

    with st.container():
        st.markdown(
            """
            <div style='padding: 0.8rem 1rem; border: 1px solid #dbeafe; border-radius: 12px; background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);'>
                <strong>Executive output:</strong> metrics are formatted for stakeholder review, exports, and presentation-ready reporting.
            </div>
            """,
            unsafe_allow_html=True,
        )

    exp_col1, exp_col2, _ = st.columns([1, 1, 2])
    summary_stats = calculate_metrics(posts)
    has_data = bool(posts)

    with exp_col1:
        excel_bytes = generate_excel_report(posts, summary_stats) if has_data else b""
        st.download_button(
            label="📊 Download Excel Report (.xlsx)",
            data=excel_bytes,
            file_name=f"instagram_report_{datetime.date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            width="stretch",
            disabled=not has_data,
            help="Add at least one Instagram URL to enable report generation."
        )

    with exp_col2:
        pdf_bytes = generate_pdf_report(posts, summary_stats) if has_data else b""
        st.download_button(
            label="📄 Download PDF Report (.pdf)",
            data=pdf_bytes,
            file_name=f"instagram_report_{datetime.date.today().isoformat()}.pdf",
            mime="application/pdf",
            type="secondary",
            width="stretch",
            disabled=not has_data,
            help="Add at least one Instagram URL to enable report generation."
        )

    if not posts:
        return

    f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
    with f_col1:
        search_query = st.text_input("🔍 Search by username or URL:", placeholder="@username or shortcode...")
    with f_col2:
        type_filter = st.selectbox("Filter by Type:", ["All Types", "Reel", "Photo", "Carousel", "Video"])
    with f_col3:
        status_filter = st.selectbox(
            "Filter by Status:",
            ["All Statuses", "Success", "Hidden likes", "API Key Required", "Failed", "Private/Not found"]
        )

    # Apply filters
    filtered = posts
    if search_query:
        q = search_query.strip().lower()
        filtered = [p for p in filtered if q in p.get("username", "").lower() or q in p.get("url", "").lower()]

    if type_filter != "All Types":
        filtered = [p for p in filtered if p.get("post_type") == type_filter]

    if status_filter != "All Statuses":
        filtered = [p for p in filtered if p.get("status") == status_filter]

    # Format table data
    display_rows = []
    for p in filtered:
        # Views
        if p.get("post_type") in ["Photo", "Carousel"]:
            views_display = "N/A"
        elif p.get("views") is not None:
            views_display = f"{p['views']:,}"
        else:
            views_display = "N/A"

        # Likes
        if p.get("status") == "Hidden likes" or (p.get("status") == "Success" and p.get("likes") is None):
            likes_display = "Hidden"
        elif p.get("likes") is not None:
            likes_display = f"{p['likes']:,}"
        else:
            likes_display = "N/A"

        # Comments
        comments_display = f"{p.get('comments'):,}" if p.get("comments") is not None else "N/A"

        # Shares
        shares_display = f"{p.get('shares'):,}" if p.get("shares") is not None else "N/A"

        display_rows.append({
            "Thumbnail": p.get("thumbnail"),
            "URL": p.get("url"),
            "Username": p.get("username", "N/A"),
            "Type": p.get("post_type", "Unknown"),
            "Views": views_display,
            "Likes": likes_display,
            "Comments": comments_display,
            "Shares": shares_display,
            "Posted At": p.get("posted_at", "N/A"),
            "Last Updated": str(p.get("fetched_at", ""))[:19].replace("T", " "),
            "Status": p.get("status", "Unknown")
        })

    df_display = pd.DataFrame(display_rows)

    st.dataframe(
        df_display,
        width="stretch",
        column_config={
            "Thumbnail": st.column_config.ImageColumn("Thumbnail", help="Post preview image"),
            "URL": st.column_config.LinkColumn("Instagram URL", display_text="Open Post ↗"),
            "Views": st.column_config.TextColumn("Views (Plays)", help="Reel plays (videoPlayCount). 'N/A' on photos."),
            "Likes": st.column_config.TextColumn("Likes", help="Like count. Shows 'Hidden' if disabled."),
            "Comments": st.column_config.TextColumn("Comments", help="Total comment count."),
            "Shares": st.column_config.TextColumn("Shares", help="Total share / reshare count."),
            "Status": st.column_config.TextColumn("Status"),
        },
        hide_index=True
    )

    st.caption(f"Showing **{len(filtered)}** of **{len(posts)}** total posts.")



if __name__ == "__main__":
    main()
