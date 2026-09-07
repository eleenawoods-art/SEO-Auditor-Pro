import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="SEO Auditor Pro",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)

UA = "SEO-Auditor-Pro/5.1"


# =========================================================
# HELPERS
# =========================================================

def normalize_url(url):
    url = url.strip()
    if not url:
        return ""
    return url if url.startswith(("http://", "https://")) else "https://" + url


def canonicalize_url(url):
    """Normalize URLs for deduplication while preserving useful paths."""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        return f"{scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")
    except Exception:
        return url


def same_site(a, b):
    try:
        return urlparse(a).netloc.lower().split(":")[0] == urlparse(b).netloc.lower().split(":")[0]
    except Exception:
        return False


def build_session():
    session = requests.Session()

    retries = Retry(
        total=1,
        connect=1,
        read=1,
        backoff_factor=0.3,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": UA})
    return session


SESSION = build_session()


def fetch(url, timeout=15, method="GET"):
    return SESSION.request(
        method,
        url,
        timeout=timeout,
        allow_redirects=True,
    )


# =========================================================
# LINK CHECKING
# =========================================================

def classify_link_status(status):
    if status is None:
        return "Unreachable"

    if 200 <= status < 300:
        return "Working"

    if 300 <= status < 400:
        return "Redirect"

    if status == 404:
        return "Broken (404)"

    if status in (401, 403):
        return f"Blocked ({status})"

    if status == 408:
        return "Timeout (408)"

    if status == 429:
        return "Rate Limited (429)"

    if 400 <= status < 500:
        return f"Client Error ({status})"

    if 500 <= status < 600:
        return f"Server Error ({status})"

    return f"HTTP {status}"


def check_link(url, timeout):
    try:
        response = fetch(url, min(timeout, 10), "HEAD")

        # Some servers do not support HEAD. Retry with GET.
        if response.status_code in (403, 405) or response.status_code >= 500:
            response = fetch(url, min(timeout, 10), "GET")

        status = response.status_code
        final_url = response.url
        redirects = len(response.history)
        state = classify_link_status(status)

        return {
            "URL": url,
            "Status": status,
            "State": state,
            "Redirects": redirects,
            "Final URL": final_url,
            "Error": "",
        }

    except requests.TooManyRedirects as exc:
        return {
            "URL": url,
            "Status": None,
            "State": "Unreachable",
            "Redirects": 0,
            "Final URL": "",
            "Error": f"Too many redirects: {exc}",
        }

    except requests.RequestException as exc:
        return {
            "URL": url,
            "Status": None,
            "State": "Unreachable",
            "Redirects": 0,
            "Final URL": "",
            "Error": str(exc),
        }


def resource_status(url, timeout):
    try:
        response = fetch(url, min(timeout, 10), "GET")
        return response.status_code
    except requests.RequestException:
        return None


def is_link_problem(state):
    return (
        state.startswith("Broken")
        or state.startswith("Server Error")
        or state == "Unreachable"
        or state.startswith("Client Error")
    )


def is_rate_limited(state):
    return state.startswith("Rate Limited") or state.startswith("Blocked")


# =========================================================
# PAGE SEO CHECKS
# =========================================================

def page_checks(soup, final_url):
    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    desc_tag = soup.find(
        "meta",
        attrs={"name": re.compile(r"^description$", re.I)},
    )
    description = desc_tag.get("content", "").strip() if desc_tag else ""

    h1 = [x.get_text(" ", strip=True) for x in soup.find_all("h1")]
    h2 = [x.get_text(" ", strip=True) for x in soup.find_all("h2")]
    h3 = [x.get_text(" ", strip=True) for x in soup.find_all("h3")]

    images = soup.find_all("img")
    missing_alt = [
        img.get("src", "")
        for img in images
        if not img.get("alt", "").strip()
    ]

    canonical = soup.find(
        "link",
        rel=lambda value: value and "canonical" in value,
    )

    viewport = soup.find(
        "meta",
        attrs={"name": re.compile(r"^viewport$", re.I)},
    )

    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")

    robots_meta = soup.find(
        "meta",
        attrs={"name": re.compile(r"^robots$", re.I)},
    )

    title_ok = 10 <= len(title) <= 60
    meta_ok = 50 <= len(description) <= 160

    h1_ok = len(h1) == 1
    images_ok = len(images) == 0 or len(missing_alt) == 0
    canonical_ok = canonical is not None
    viewport_ok = viewport is not None
    og_ok = bool(og_title and og_description)

    checks = [
        (
            "HTTPS",
            final_url.startswith("https://"),
            "Secure HTTPS connection detected."
            if final_url.startswith("https://")
            else "Page is not using HTTPS.",
        ),
        (
            "Title",
            title_ok,
            f"Current length: {len(title)} characters."
            if title
            else "Title tag is missing.",
        ),
        (
            "Meta Description",
            meta_ok,
            f"Current length: {len(description)} characters."
            if description
            else "Meta description is missing.",
        ),
        (
            "H1 Structure",
            h1_ok,
            f"Found {len(h1)} H1 tag(s)."
            if h1_ok
            else f"Found {len(h1)} H1 tag(s). Recommended: exactly 1.",
        ),
        (
            "Image ALT Text",
            images_ok,
            "All images have ALT text."
            if len(images) > 0
            else "No images found (N/A).",
        ),
        (
            "Canonical",
            canonical_ok,
            "Canonical tag found."
            if canonical_ok
            else "Canonical tag is missing.",
        ),
        (
            "Viewport",
            viewport_ok,
            "Viewport tag found."
            if viewport_ok
            else "Viewport tag is missing.",
        ),
        (
            "Open Graph",
            og_ok,
            "OG title and description found."
            if og_ok
            else "Open Graph data is incomplete.",
        ),
        (
            "Robots Meta",
            True,
            "Robots meta tag found."
            if robots_meta
            else "No robots meta tag found; search engines will use default behavior.",
        ),
    ]

    return {
        "title": title,
        "description": description,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "images": images,
        "missing_alt": missing_alt,
        "canonical": canonical,
        "viewport": viewport,
        "og_title": og_title,
        "og_description": og_description,
        "robots_meta": robots_meta,
        "checks": checks,
    }


# =========================================================
# CRAWLER
# =========================================================

def crawl_site(start_url, max_pages, timeout):
    start_url = normalize_url(start_url)

    queue = deque([start_url])
    queued = {canonicalize_url(start_url)}
    visited = set()
    pages = []

    progress = st.progress(0, text="Crawling website...")

    while queue and len(pages) < max_pages:
        current = queue.popleft()
        current_key = canonicalize_url(current)

        if current_key in visited:
            continue

        try:
            response = fetch(current, timeout, "GET")
            final_url = response.url

            if not same_site(start_url, final_url):
                visited.add(current_key)
                continue

            if response.status_code >= 400:
                visited.add(current_key)
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            info = page_checks(soup, final_url)

            final_key = canonicalize_url(final_url)

            # Prevent duplicate pages caused by redirects.
            if final_key not in {
                canonicalize_url(p["URL"]) for p in pages
            }:
                pages.append(
                    {
                        "URL": final_url,
                        "Status": response.status_code,
                        "Title": info["title"],
                        "Meta Description": info["description"],
                        "H1 Count": len(info["h1"]),
                        "H2 Count": len(info["h2"]),
                        "H3 Count": len(info["h3"]),
                        "Images": len(info["images"]),
                        "Missing ALT": len(info["missing_alt"]),
                        "Canonical": "Yes" if info["canonical"] else "No",
                    }
                )

            visited.add(current_key)

            for anchor in soup.find_all("a", href=True):
                raw_href = anchor.get("href", "").strip()

                if not raw_href:
                    continue

                if raw_href.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                target = urljoin(final_url, raw_href).split("#")[0]
                parsed = urlparse(target)

                if parsed.scheme not in ("http", "https"):
                    continue

                if not same_site(start_url, target):
                    continue

                target_key = canonicalize_url(target)

                if target_key not in queued and len(queued) < max_pages * 4:
                    queued.add(target_key)
                    queue.append(target)

        except requests.RequestException:
            visited.add(current_key)

        except Exception:
            visited.add(current_key)

        progress.progress(
            min(len(pages) / max_pages, 1.0),
            text=f"Crawling pages: {len(pages)}/{max_pages}",
        )

    progress.empty()
    return pages


# =========================================================
# SCORING
# =========================================================

def calculate_scores(checks, link_results, image_count):
    check_map = {name: ok for name, ok, _ in checks}

    def passed(name):
        return bool(check_map.get(name, False))

    technical_items = [
        passed("HTTPS"),
        passed("Canonical"),
        passed("Viewport"),
    ]

    onpage_items = [
        passed("Title"),
        passed("Meta Description"),
        passed("H1 Structure"),
    ]

    social_items = [
        passed("Viewport"),
        passed("Open Graph"),
    ]

    technical = round(sum(technical_items) / len(technical_items) * 100)
    onpage = round(sum(onpage_items) / len(onpage_items) * 100)
    social = round(sum(social_items) / len(social_items) * 100)

    if image_count == 0:
        image_score = None
    else:
        image_score = 100 if passed("Image ALT Text") else 50

    scores = {
        "Technical SEO": technical,
        "On-Page SEO": onpage,
        "Images": image_score,
        "Social/Mobile": social,
    }

    if link_results:
        serious_problems = sum(
            1 for item in link_results if is_link_problem(item["State"])
        )

        scores["Links"] = round(
            (len(link_results) - serious_problems)
            / len(link_results)
            * 100
        )

    weights = {
        "Technical SEO": 0.30,
        "On-Page SEO": 0.30,
        "Images": 0.10,
        "Social/Mobile": 0.10,
        "Links": 0.20,
    }

    numerator = 0
    denominator = 0

    for key, weight in weights.items():
        value = scores.get(key)

        if value is not None:
            numerator += value * weight
            denominator += weight

    overall = round(numerator / denominator) if denominator else 0

    return scores, overall


# =========================================================
# REPORT DATA
# =========================================================

def make_check_rows(checks):
    rows = []

    for name, passed, detail in checks:
        rows.append(
            {
                "Section": "SEO Checks",
                "Check": name,
                "Status": "PASS" if passed else "NEEDS WORK",
                "Details": detail,
            }
        )

    return rows


def make_link_rows(link_results):
    rows = []

    for item in link_results:
        rows.append(
            {
                "Section": "Link Analysis",
                "Check": "",
                "Status": item["Status"] if item["Status"] is not None else "",
                "Details": "",
                "URL": item["URL"],
                "State": item["State"],
                "Redirects": item["Redirects"],
                "Final URL": item["Final URL"],
                "Error": item["Error"],
            }
        )

    return rows


def make_crawl_rows(crawl_pages):
    rows = []

    for page in crawl_pages:
        rows.append(
            {
                "Section": "Crawled Pages",
                "Check": "",
                "Status": page["Status"],
                "Details": "",
                "URL": page["URL"],
                "State": "",
                "Redirects": "",
                "Final URL": "",
                "Error": "",
                "Title": page["Title"],
                "Meta Description": page["Meta Description"],
                "H1 Count": page["H1 Count"],
                "H2 Count": page["H2 Count"],
                "H3 Count": page["H3 Count"],
                "Images": page["Images"],
                "Missing ALT": page["Missing ALT"],
                "Canonical": page["Canonical"],
            }
        )

    return rows


def build_findings_dataframe(checks, link_results, crawl_pages):
    rows = []

    rows.extend(make_check_rows(checks))
    rows.extend(make_link_rows(link_results))
    rows.extend(make_crawl_rows(crawl_pages))

    if not rows:
        return pd.DataFrame()

    columns = [
        "Section",
        "Check",
        "Status",
        "Details",
        "URL",
        "State",
        "Redirects",
        "Final URL",
        "Error",
        "Title",
        "Meta Description",
        "H1 Count",
        "H2 Count",
        "H3 Count",
        "Images",
        "Missing ALT",
        "Canonical",
    ]

    df = pd.DataFrame(rows)

    for column in columns:
        if column not in df.columns:
            df[column] = ""

    return df[columns]


# =========================================================
# UI
# =========================================================

st.title("🔎 SEO Auditor Pro")
st.caption("Professional Website SEO Analysis & Technical Audit")

with st.sidebar:
    st.header("⚙️ Audit Settings")

    timeout = st.slider(
        "Request timeout (seconds)",
        min_value=5,
        max_value=30,
        value=15,
    )

    run_links = st.checkbox(
        "Run Full Broken Link Checker",
        value=True,
    )

    run_crawler = st.checkbox(
        "Crawl Website Pages",
        value=True,
    )

    max_pages = st.slider(
        "Maximum pages to crawl",
        min_value=1,
        max_value=50,
        value=10,
    )

    st.info(
        "Analyze on-page SEO, technical signals, links, images, "
        "social/mobile data, and same-domain pages from one dashboard."
    )

    st.markdown("---")
    st.markdown("**Included features**")
    st.caption(
        "SEO scorecard • Broken-link checker • Redirect detection • "
        "Website crawler • CSV report"
    )


website_url = st.text_input(
    "Website URL",
    placeholder="https://example.com",
)

client_name = st.text_input(
    "Client / Project Name",
    placeholder="Client Website",
)


# =========================================================
# RUN AUDIT
# =========================================================

if st.button("🚀 Run Complete Website Audit", type="primary", use_container_width=True):

    if not website_url.strip():
        st.warning("Please enter a website URL.")

    else:
        try:
            normalized = normalize_url(website_url)

            with st.spinner("Running complete audit..."):

                # -------------------------------------------------
                # MAIN PAGE
                # -------------------------------------------------

                first_response = fetch(normalized, timeout, "GET")
                soup = BeautifulSoup(first_response.text, "html.parser")
                final_url = first_response.url

                info = page_checks(soup, final_url)

                # -------------------------------------------------
                # LINK DISCOVERY
                # -------------------------------------------------

                links = []
                seen = set()

                for anchor in soup.find_all("a", href=True):
                    raw_href = anchor.get("href", "").strip()

                    if not raw_href:
                        continue

                    if raw_href.startswith(
                        ("#", "mailto:", "tel:", "javascript:")
                    ):
                        continue

                    target = urljoin(final_url, raw_href).split("#")[0]
                    parsed = urlparse(target)

                    if parsed.scheme not in ("http", "https"):
                        continue

                    target_key = canonicalize_url(target)

                    if target_key not in seen:
                        seen.add(target_key)
                        links.append(target)

                # -------------------------------------------------
                # LINK CHECKING
                # -------------------------------------------------

                link_results = []

                if run_links and links:

                    progress = st.progress(
                        0,
                        text="Checking page links...",
                    )

                    with ThreadPoolExecutor(max_workers=12) as executor:

                        futures = [
                            executor.submit(
                                check_link,
                                link,
                                min(timeout, 10),
                            )
                            for link in links
                        ]

                        total = len(futures)

                        for i, future in enumerate(
                            as_completed(futures),
                            1,
                        ):
                            try:
                                link_results.append(future.result())
                            except Exception as exc:
                                link_results.append(
                                    {
                                        "URL": "",
                                        "Status": None,
                                        "State": "Unreachable",
                                        "Redirects": 0,
                                        "Final URL": "",
                                        "Error": str(exc),
                                    }
                                )

                            progress.progress(
                                i / total,
                                text=f"Checking links: {i}/{total}",
                            )

                    progress.empty()

                # -------------------------------------------------
                # ROBOTS / SITEMAP
                # -------------------------------------------------

                robots_url = urljoin(final_url, "/robots.txt")
                sitemap_url = urljoin(final_url, "/sitemap.xml")

                robots = resource_status(robots_url, timeout)
                sitemap = resource_status(sitemap_url, timeout)

                info["checks"].extend(
                    [
                        (
                            "Robots.txt",
                            robots == 200,
                            f"HTTP status: {robots if robots is not None else 'unavailable'}.",
                        ),
                        (
                            "Sitemap.xml",
                            sitemap == 200,
                            f"HTTP status: {sitemap if sitemap is not None else 'unavailable'}.",
                        ),
                    ]
                )

                # -------------------------------------------------
                # SCORE
                # -------------------------------------------------

                scores, overall = calculate_scores(
                    info["checks"],
                    link_results,
                    len(info["images"]),
                )

                # -------------------------------------------------
                # CRAWLER
                # -------------------------------------------------

                if run_crawler:
                    crawl_pages = crawl_site(
                        final_url,
                        max_pages,
                        timeout,
                    )
                else:
                    crawl_pages = []

            # =====================================================
            # RESULTS
            # =====================================================

            st.success("✅ Complete audit finished successfully.")

            broken = [
                item
                for item in link_results
                if is_link_problem(item["State"])
            ]

            redirects = [
                item
                for item in link_results
                if item["Redirects"] > 0
            ]

            rate_limited = [
                item
                for item in link_results
                if is_rate_limited(item["State"])
            ]

            # -----------------------------------------------------
            # TOP METRICS
            # -----------------------------------------------------

            c1, c2, c3, c4, c5 = st.columns(5)

            c1.metric("Overall SEO", f"{overall}/100")
            c2.metric("HTTP Status", first_response.status_code)
            c3.metric("Total Links", len(links))
            c4.metric("Broken / Errors", len(broken))
            c5.metric("Redirects", len(redirects))

            if rate_limited:
                st.info(
                    f"ℹ️ {len(rate_limited)} link(s) returned blocked/rate-limited "
                    "responses. These are not automatically treated as confirmed broken pages."
                )

            # -----------------------------------------------------
            # SCORECARD
            # -----------------------------------------------------

            st.subheader("📊 Professional SEO Scorecard")

            display_scores = list(scores.items())
            cols = st.columns(len(display_scores))

            for col, (name, value) in zip(cols, display_scores):
                if value is None:
                    col.metric(name, "N/A")
                    col.caption("No images found")
                else:
                    col.metric(name, f"{value}/100")
                    col.progress(value / 100)

            if overall >= 80:
                st.success("🟢 Excellent SEO foundation.")
            elif overall >= 60:
                st.warning(
                    "🟡 Good foundation with several improvements recommended."
                )
            else:
                st.error(
                    "🔴 Major SEO improvements are recommended."
                )

            # -----------------------------------------------------
            # PAGE OVERVIEW
            # -----------------------------------------------------

            st.subheader("🧾 Page Overview")

            overview1, overview2 = st.columns(2)

            with overview1:
                st.write("**Final URL:**", final_url)
                st.write(
                    "**Title:**",
                    info["title"] or "Missing",
                )
                st.write(
                    "**Meta Description:**",
                    info["description"] or "Missing",
                )

            with overview2:
                st.write(
                    "**H1:**",
                    " | ".join(info["h1"])
                    if info["h1"]
                    else "Missing",
                )
                st.write("**H1 count:**", len(info["h1"]))
                st.write("**H2 count:**", len(info["h2"]))
                st.write("**H3 count:**", len(info["h3"]))

            # -----------------------------------------------------
            # SEO CHECKS - SEPARATE TABLE
            # -----------------------------------------------------

            st.subheader("🔍 SEO Checks")

            check_rows = []

            for name, passed, detail in info["checks"]:
                check_rows.append(
                    {
                        "Check": name,
                        "Status": "✅ PASS" if passed else "⚠️ NEEDS WORK",
                        "Details": detail,
                    }
                )

            checks_df = pd.DataFrame(check_rows)

            st.dataframe(
                checks_df,
                use_container_width=True,
                hide_index=True,
            )

            # -----------------------------------------------------
            # LINK ANALYSIS
            # -----------------------------------------------------

            if run_links:
                st.subheader("🔗 Link Analysis")

                if link_results:

                    link_df = pd.DataFrame(link_results)

                    link_display = link_df[
                        [
                            "URL",
                            "Status",
                            "State",
                            "Redirects",
                            "Final URL",
                            "Error",
                        ]
                    ].copy()

                    st.dataframe(
                        link_display,
                        use_container_width=True,
                        hide_index=True,
                    )

                else:
                    st.info("No links were found on the audited page.")

            # -----------------------------------------------------
            # CRAWLED PAGES
            # -----------------------------------------------------

            if run_crawler:
                st.subheader("🕷️ Crawled Pages")

                if crawl_pages:
                    crawl_df = pd.DataFrame(crawl_pages)

                    st.dataframe(
                        crawl_df,
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No additional same-domain pages were crawled.")

            # -----------------------------------------------------
            # ACTION PLAN
            # -----------------------------------------------------

            st.subheader("🛠️ Recommended Action Plan")

            action_items = []

            for name, passed, detail in info["checks"]:
                if not passed:
                    recommendations = {
                        "HTTPS": "Enable HTTPS and redirect HTTP URLs to HTTPS.",
                        "Title": "Add or optimize the page title to approximately 10–60 characters.",
                        "Meta Description": "Add a useful meta description of approximately 50–160 characters.",
                        "H1 Structure": "Use one clear primary H1 heading for the page.",
                        "Image ALT Text": "Add descriptive ALT text to images that need accessibility/SEO context.",
                        "Canonical": "Add a valid canonical URL to identify the preferred version of the page.",
                        "Viewport": "Add a responsive viewport meta tag for mobile usability.",
                        "Open Graph": "Add og:title and og:description for better social sharing previews.",
                        "Robots.txt": "Review and publish a valid robots.txt file.",
                        "Sitemap.xml": "Create or expose an XML sitemap and reference it from robots.txt.",
                    }

                    action_items.append(
                        recommendations.get(
                            name,
                            f"Review the {name} check.",
                        )
                    )

            if broken:
                action_items.append(
                    f"Review {len(broken)} link(s) returning confirmed HTTP/client/server errors."
                )

            if redirects:
                action_items.append(
                    f"Review {len(redirects)} redirected link(s) and update internal links where practical."
                )

            if not action_items:
                st.success(
                    "🎉 No major action items were detected by the current checks."
                )
            else:
                for i, item in enumerate(action_items, 1):
                    st.markdown(f"**{i}.** {item}")

            # -----------------------------------------------------
            # PROFESSIONAL CSV EXPORT
            # -----------------------------------------------------

            st.subheader("📥 Export Report")

            findings_df = build_findings_dataframe(
                info["checks"],
                link_results,
                crawl_pages,
            )

            csv_data = findings_df.to_csv(
                index=False,
                encoding="utf-8-sig",
            )

            safe_client = (
                (client_name.strip() or "Client")
                .replace(" ", "_")
                .replace("/", "_")
                .replace("\\", "_")
            )

            st.download_button(
                "📥 Download Professional CSV Report",
                data=csv_data,
                file_name=f"SEO_Audit_Report_{safe_client}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        except requests.RequestException as exc:
            st.error(
                "❌ Unable to access the website. "
                f"Please check the URL and try again.\n\nDetails: {exc}"
            )

        except Exception as exc:
            st.error(
                "❌ Audit failed unexpectedly."
            )
            st.exception(exc)
