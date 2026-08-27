import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="SEO Auditor Pro",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# CONSTANTS
# =========================================================

UA = "SEO-Auditor-Pro/5.0"


# =========================================================
# URL HELPERS
# =========================================================

def normalize_url(url):
    url = url.strip()

    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url.rstrip("/")


def same_site(a, b):
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()


# =========================================================
# HTTP FETCH
# =========================================================

def fetch(url, timeout=15, method="GET"):
    return requests.request(
        method,
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=timeout,
        allow_redirects=True,
    )


# =========================================================
# LINK CHECKER
# =========================================================

def check_link(url, timeout):
    try:
        response = fetch(url, timeout, "HEAD")

        if response.status_code in (403, 405) or response.status_code >= 500:
            response = fetch(url, timeout, "GET")

        status = response.status_code
        final_url = response.url
        redirects = len(response.history)

        if 200 <= status < 300:
            state = "Working"

        elif 300 <= status < 400:
            state = "Redirect"

        elif status == 404:
            state = "Broken (404)"

        elif status >= 400:
            state = f"Broken ({status})"

        else:
            state = "Unknown"

        return {
            "URL": url,
            "Status": status,
            "State": state,
            "Redirects": redirects,
            "Final URL": final_url,
            "Error": "",
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


# =========================================================
# RESOURCE STATUS
# =========================================================

def resource_status(url, timeout):
    try:
        response = fetch(url, min(timeout, 10), "GET")
        return response.status_code

    except requests.RequestException:
        return None


# =========================================================
# PAGE SEO CHECKS
# =========================================================

def page_checks(soup, final_url):

    # -----------------------------
    # Basic SEO elements
    # -----------------------------

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else ""
    )

    desc_tag = soup.find(
        "meta",
        attrs={"name": re.compile(r"^description$", re.I)},
    )

    description = (
        desc_tag.get("content", "").strip()
        if desc_tag
        else ""
    )

    h1 = [
        element.get_text(" ", strip=True)
        for element in soup.find_all("h1")
    ]

    h2 = [
        element.get_text(" ", strip=True)
        for element in soup.find_all("h2")
    ]

    h3 = [
        element.get_text(" ", strip=True)
        for element in soup.find_all("h3")
    ]

    # -----------------------------
    # Images
    # -----------------------------

    images = soup.find_all("img")

    missing_alt = [
        img.get("src", "")
        for img in images
        if not img.get("alt", "").strip()
    ]

    # -----------------------------
    # Technical
    # -----------------------------

    canonical = soup.find(
        "link",
        rel=lambda value: (
            value
            and (
                "canonical" in value
                if isinstance(value, str)
                else "canonical" in value
            )
        ),
    )

    viewport = soup.find(
        "meta",
        attrs={"name": re.compile(r"^viewport$", re.I)},
    )

    # -----------------------------
    # Open Graph
    # -----------------------------

    og_title = soup.find(
        "meta",
        attrs={"property": re.compile(r"^og:title$", re.I)},
    )

    og_description = soup.find(
        "meta",
        attrs={"property": re.compile(r"^og:description$", re.I)},
    )

    # -----------------------------
    # Check logic
    # -----------------------------

    title_ok = 10 <= len(title) <= 60

    meta_ok = 50 <= len(description) <= 160

    h1_status = (
        "PASS"
        if len(h1) == 1
        else "WARNING"
        if len(h1) > 1
        else "ERROR"
    )

    checks = [

        (
            "HTTPS",
            final_url.startswith("https://"),
            (
                "Secure HTTPS connection detected."
                if final_url.startswith("https://")
                else "HTTPS is not being used."
            ),
        ),

        (
            "Title",
            title_ok,
            (
                f"Current length: {len(title)} characters."
                if title
                else "Title tag is missing."
            ),
        ),

        (
            "Meta Description",
            meta_ok,
            (
                f"Current length: {len(description)} characters."
                if description
                else "Meta description is missing."
            ),
        ),

        (
            "H1 Structure",
            h1_status == "PASS",
            f"Found {len(h1)} H1 tag(s). {h1_status}.",
        ),

        (
            "Image ALT Text",
            len(images) == 0 or len(missing_alt) == 0,
            (
                "No images found (N/A)."
                if len(images) == 0
                else f"{len(missing_alt)} image(s) missing ALT text."
            ),
        ),

        (
            "Canonical",
            canonical is not None,
            (
                "Canonical tag found."
                if canonical
                else "Canonical tag missing."
            ),
        ),

        (
            "Viewport",
            viewport is not None,
            (
                "Viewport tag found."
                if viewport
                else "Viewport tag missing."
            ),
        ),

        (
            "Open Graph",
            bool(og_title and og_description),
            (
                "OG title and description found."
                if og_title and og_description
                else "Open Graph data is incomplete."
            ),
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
        "checks": checks,
    }


# =========================================================
# WEBSITE CRAWLER
# =========================================================

def crawl_site(start_url, max_pages, timeout):

    start_url = normalize_url(start_url)

    queue = deque([start_url])
    queued = {start_url}
    visited = set()
    pages = []

    progress = st.progress(
        0,
        text="Crawling website...",
    )

    while queue and len(visited) < max_pages:

        current = queue.popleft()

        if current in visited:
            continue

        try:

            response = fetch(
                current,
                timeout,
                "GET",
            )

            final_url = response.url

            if not same_site(start_url, final_url):
                visited.add(current)
                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            info = page_checks(
                soup,
                final_url,
            )

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
                    "Canonical": (
                        "Yes"
                        if info["canonical"]
                        else "No"
                    ),
                }
            )

            visited.add(current)

            # -----------------------------
            # Discover internal links
            # -----------------------------

            for anchor in soup.find_all(
                "a",
                href=True,
            ):

                target = urljoin(
                    final_url,
                    anchor["href"],
                ).split("#")[0]

                parsed = urlparse(target)

                if (
                    parsed.scheme in ("http", "https")
                    and same_site(start_url, target)
                ):

                    if (
                        target not in queued
                        and len(queued) < max_pages * 3
                    ):
                        queued.add(target)
                        queue.append(target)

        except requests.RequestException:
            visited.add(current)

        except Exception:
            visited.add(current)

        progress.progress(
            min(
                len(visited) / max_pages,
                1.0,
            ),
            text=(
                f"Crawling pages: "
                f"{len(visited)}/{max_pages}"
            ),
        )

    progress.empty()

    return pages


# =========================================================
# SCORE CALCULATION
# =========================================================

def calculate_scores(
    checks,
    link_results,
    image_count,
):

    def passed(name):

        for check_name, ok, _ in checks:

            if check_name == name:
                return bool(ok)

        return False

    # -----------------------------
    # Category scores
    # -----------------------------

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

    technical = round(
        sum(technical_items)
        / len(technical_items)
        * 100
    )

    onpage = round(
        sum(onpage_items)
        / len(onpage_items)
        * 100
    )

    social = round(
        sum(social_items)
        / len(social_items)
        * 100
    )

    # -----------------------------
    # Image score
    # -----------------------------

    if image_count == 0:

        image_score = None

    else:

        image_score = (
            100
            if passed("Image ALT Text")
            else 50
        )

    scores = {
        "Technical SEO": technical,
        "On-Page SEO": onpage,
        "Images": image_score,
        "Social/Mobile": social,
    }

    # -----------------------------
    # Link score
    # -----------------------------

    if link_results:

        broken = sum(
            1
            for item in link_results
            if (
                item["State"].startswith("Broken")
                or item["State"] == "Unreachable"
            )
        )

        scores["Links"] = round(
            (
                (len(link_results) - broken)
                / len(link_results)
            )
            * 100
        )

    # -----------------------------
    # Weighted overall score
    # -----------------------------

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

    overall = (
        round(numerator / denominator)
        if denominator
        else 0
    )

    return scores, overall


# =========================================================
# MAIN UI
# =========================================================

st.title("🔎 SEO Auditor Pro")

st.caption(
    "Professional Website SEO Analysis"
)


# =========================================================
# SIDEBAR
# =========================================================

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
        "Analyze on-page SEO, technical signals, "
        "links, images, social/mobile data, and "
        "same-domain pages from one dashboard."
    )

    st.markdown("---")

    st.markdown("**Included features**")

    st.caption(
        "SEO scorecard • Broken-link checker • "
        "Redirect detection • Website crawler • "
        "CSV report"
    )


# =========================================================
# WEBSITE INPUT
# =========================================================

website_url = st.text_input(
    "Website URL",
    placeholder="https://example.com",
)


# =========================================================
# RUN AUDIT
# =========================================================

if st.button(
    "🚀 Run Complete Website Audit",
    type="primary",
    use_container_width=True,
):

    if not website_url.strip():

        st.warning(
            "Please enter a website URL."
        )

    else:

        try:

            normalized_start_url = normalize_url(
                website_url
            )

            # =================================================
            # FIRST PAGE
            # =================================================

            with st.spinner(
                "Connecting to website..."
            ):

                first_response = fetch(
                    normalized_start_url,
                    timeout,
                    "GET",
                )

                first_response.raise_for_status()

                soup = BeautifulSoup(
                    first_response.text,
                    "html.parser",
                )

                final_url = first_response.url

                info = page_checks(
                    soup,
                    final_url,
                )

            # =================================================
            # COLLECT LINKS
            # =================================================

            links = []
            seen = set()

            for anchor in soup.find_all(
                "a",
                href=True,
            ):

                target = urljoin(
                    final_url,
                    anchor["href"],
                ).split("#")[0]

                parsed = urlparse(target)

                if (
                    parsed.scheme in ("http", "https")
                    and target not in seen
                ):

                    seen.add(target)
                    links.append(target)

            # =================================================
            # LINK CHECKER
            # =================================================

            link_results = []

            if run_links and links:

                progress = st.progress(
                    0,
                    text="Checking all page links...",
                )

                max_workers = min(
                    12,
                    max(1, len(links)),
                )

                with ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:

                    futures = [
                        executor.submit(
                            check_link,
                            link,
                            min(timeout, 10),
                        )
                        for link in links
                    ]

                    total = len(futures)

                    for index, future in enumerate(
                        as_completed(futures),
                        1,
                    ):

                        try:
                            link_results.append(
                                future.result()
                            )

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
                            index / total,
                            text=(
                                f"Checking links: "
                                f"{index}/{total}"
                            ),
                        )

                progress.empty()

            # =================================================
            # ROBOTS + SITEMAP
            # =================================================

            robots = resource_status(
                urljoin(
                    final_url,
                    "/robots.txt",
                ),
                timeout,
            )

            sitemap = resource_status(
                urljoin(
                    final_url,
                    "/sitemap.xml",
                ),
                timeout,
            )

            info["checks"].extend(
                [
                    (
                        "Robots.txt",
                        robots == 200,
                        f"HTTP status: "
                        f"{robots if robots is not None else 'unavailable'}.",
                    ),
                    (
                        "Sitemap.xml",
                        sitemap == 200,
                        f"HTTP status: "
                        f"{sitemap if sitemap is not None else 'unavailable'}.",
                    ),
                ]
            )

            # =================================================
            # SCORE
            # =================================================

            scores, overall = calculate_scores(
                info["checks"][:8],
                link_results,
                len(info["images"]),
            )

            # =================================================
            # CRAWLER
            # =================================================

            if run_crawler:

                crawl_pages = crawl_site(
                    final_url,
                    max_pages,
                    timeout,
                )

            else:

                crawl_pages = []

            # =================================================
            # SUCCESS
            # =================================================

            st.success(
                "Complete audit finished successfully."
            )

            # =================================================
            # LINK SUMMARY
            # =================================================

            broken = [
                item
                for item in link_results
                if (
                    item["State"].startswith("Broken")
                    or item["State"] == "Unreachable"
                )
            ]

            redirects = [
                item
                for item in link_results
                if item["Redirects"] > 0
            ]

            # =================================================
            # TOP METRICS
            # =================================================

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Overall SEO",
                f"{overall}/100",
            )

            c2.metric(
                "HTTP Status",
                first_response.status_code,
            )

            c3.metric(
                "Total Links",
                len(links),
            )

            c4.metric(
                "Broken Links",
                len(broken),
            )

            # =================================================
            # SCORECARD
            # =================================================

            st.subheader(
                "📊 Professional SEO Scorecard"
            )

            display_scores = list(
                scores.items()
            )

            score_columns = st.columns(
                len(display_scores)
            )

            for col, (name, value) in zip(
                score_columns,
                display_scores,
            ):

                if value is None:

                    col.metric(
                        name,
                        "N/A",
                    )

                    col.caption(
                        "No images found"
                    )

                else:

                    col.metric(
                        name,
                        f"{value}/100",
                    )

                    col.progress(
                        value / 100
                    )

            # =================================================
            # OVERALL MESSAGE
            # =================================================

            if overall >= 80:

                st.success(
                    "Excellent SEO foundation."
                )

            elif overall >= 60:

                st.warning(
                    "Good foundation with several "
                    "improvements recommended."
                )

            else:

                st.error(
                    "Major SEO improvements are recommended."
                )

            # =================================================
            # PAGE OVERVIEW
            # =================================================

            st.subheader(
                "🧾 Page Overview"
            )

            st.write(
                "**Final URL:**",
                final_url,
            )

            st.write(
                "**Title:**",
                info["title"] or "Missing",
            )

            st.write(
                "**Meta Description:**",
                info["description"] or "Missing",
            )

            st.write(
                "**H1:**",
                (
                    " | ".join(info["h1"])
                    if info["h1"]
                    else "Missing"
                ),
            )

            st.write(
                "**H1 count:**",
                len(info["h1"]),
            )

            st.write(
                "**H2 count:**",
                len(info["h2"]),
            )

            st.write(
                "**H3 count:**",
                len(info["h3"]),
            )

            # =================================================
            # SEO CHECKS
            # =================================================

            st.subheader(
                "🔍 SEO Checks"
            )

            check_rows = []

            for name, passed, detail in info["checks"]:

                check_rows.append(
                    {
                        "Check": name,
                        "Status": (
                            "PASS"
                            if passed
                            else "NEEDS WORK"
                        ),
                        "Details": detail,
                    }
                )

            findings_df = pd.DataFrame(
                check_rows
            )

            filter_status = st.selectbox(
                "Filter SEO Checks",
                [
                    "All",
                    "PASS",
                    "NEEDS WORK",
                ],
                key="seo_check_filter",
            )

            if filter_status == "All":

                filtered_df = findings_df.copy()

            else:

                filtered_df = findings_df[
                    findings_df["Status"]
                    == filter_status
                ].copy()

            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
            )

            # =================================================
            # CRAWLED PAGES
            # =================================================

            if run_crawler:

                st.subheader(
                    "🕷️ Crawled Pages"
                )

                if crawl_pages:

                    crawl_df = pd.DataFrame(
                        crawl_pages
                    )

                    st.dataframe(
                        crawl_df,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.caption(
                        f"{len(crawl_pages)} page(s) "
                        f"analyzed out of a maximum "
                        f"of {max_pages}."
                    )

                else:

                    st.info(
                        "No same-domain pages were "
                        "successfully crawled."
                    )

            # =================================================
            # LINK ANALYSIS
            # =================================================

            if run_links:

                st.subheader(
                    "🔗 Link Analysis"
                )

                if link_results:

                    link_df = pd.DataFrame(
                        link_results
                    )

                    link_filter = st.selectbox(
                        "Filter Links",
                        [
                            "All",
                            "Working",
                            "Redirect",
                            "Broken",
                            "Unreachable",
                        ],
                        key="link_filter",
                    )

                    if link_filter == "Working":

                        display_links = link_df[
                            link_df["State"]
                            == "Working"
                        ]

                    elif link_filter == "Redirect":

                        display_links = link_df[
                            link_df["Redirects"] > 0
                        ]

                    elif link_filter == "Broken":

                        display_links = link_df[
                            link_df["State"].str.startswith(
                                "Broken",
                                na=False,
                            )
                        ]

                    elif link_filter == "Unreachable":

                        display_links = link_df[
                            link_df["State"]
                            == "Unreachable"
                        ]

                    else:

                        display_links = link_df

                    st.dataframe(
                        display_links,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.caption(
                        f"Checked {len(link_results)} "
                        f"link(s): {len(broken)} "
                        f"broken/unreachable, "
                        f"{len(redirects)} redirect(s)."
                    )

                else:

                    st.info(
                        "No links were found or "
                        "link checking was disabled."
                    )

            # =================================================
            # TECHNICAL RESOURCES
            # =================================================

            st.subheader(
                "⚙️ Technical Resources"
            )

            resource_df = pd.DataFrame(
                [
                    {
                        "Resource": "robots.txt",
                        "Status": (
                            "Available"
                            if robots == 200
                            else "Missing / Unavailable"
                        ),
                        "HTTP Status": (
                            robots
                            if robots is not None
                            else "N/A"
                        ),
                    },
                    {
                        "Resource": "sitemap.xml",
                        "Status": (
                            "Available"
                            if sitemap == 200
                            else "Missing / Unavailable"
                        ),
                        "HTTP Status": (
                            sitemap
                            if sitemap is not None
                            else "N/A"
                        ),
                    },
                ]
            )

            st.dataframe(
                resource_df,
                use_container_width=True,
                hide_index=True,
            )

            # =================================================
            # CSV EXPORT
            # =================================================

            st.subheader(
                "📥 Export Report"
            )

            csv_sections = []

            # SEO checks
            seo_export = findings_df.copy()
            seo_export.insert(
                0,
                "Section",
                "SEO Checks",
            )

            csv_sections.append(
                seo_export
            )

            # Link results
            if link_results:

                link_export = pd.DataFrame(
                    link_results
                )

                link_export.insert(
                    0,
                    "Section",
                    "Link Analysis",
                )

                csv_sections.append(
                    link_export
                )

            # Crawl results
            if crawl_pages:

                crawl_export = pd.DataFrame(
                    crawl_pages
                )

                crawl_export.insert(
                    0,
                    "Section",
                    "Crawled Pages",
                )

                csv_sections.append(
                    crawl_export
                )

            # Combine exports safely
            export_df = pd.concat(
                csv_sections,
                ignore_index=True,
                sort=False,
            )

            csv_data = export_df.to_csv(
                index=False,
                encoding="utf-8-sig",
            )

            st.download_button(
                "📥 Download CSV Report",
                data=csv_data,
                file_name="SEO_Audit_Report.csv",
                mime="text/csv",
                use_container_width=True,
            )

        except requests.RequestException as exc:

            st.error(
                "Unable to access the website."
            )

            st.caption(
                f"Request error: {exc}"
            )

        except Exception as exc:

            st.error(
                "The audit could not be completed."
            )

            st.caption(
                f"Error: {exc}"
            )
