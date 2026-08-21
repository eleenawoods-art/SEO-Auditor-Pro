import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="SEO Auditor Pro", page_icon="🔎", layout="wide")

UA = "SEO-Auditor-Pro/3.0"

def normalize_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url

def fetch(url, timeout):
    return requests.get(
        url,
        headers={"User-Agent": UA},
        timeout=timeout,
        allow_redirects=True
    )

def check_link(url, timeout):
    try:
        r = requests.get(
            url,
            headers={"User-Agent": UA},
            timeout=timeout,
            allow_redirects=True,
            stream=True
        )
        status = r.status_code
        final_url = r.url
        r.close()

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
            "Final URL": final_url
        }
    except requests.RequestException as exc:
        return {
            "URL": url,
            "Status": None,
            "State": "Unreachable",
            "Final URL": "",
            "Error": str(exc)
        }

def resource_status(url, timeout):
    try:
        r = fetch(url, min(timeout, 10))
        return r.status_code
    except requests.RequestException:
        return None

def audit(url, timeout, run_link_checker):
    response = fetch(normalize_url(url), timeout)
    soup = BeautifulSoup(response.text, "html.parser")
    final_url = response.url
    host = urlparse(final_url).netloc

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    meta = soup.find(
        "meta",
        attrs={"name": re.compile(r"^description$", re.I)}
    )
    description = meta.get("content", "").strip() if meta else ""

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
        rel=lambda value: value and "canonical" in value
    )
    viewport = soup.find(
        "meta",
        attrs={"name": re.compile(r"^viewport$", re.I)}
    )
    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")

    links = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        target = urljoin(final_url, anchor["href"])
        parsed = urlparse(target)

        if parsed.scheme not in ("http", "https"):
            continue

        target = target.split("#")[0]

        if target not in seen:
            seen.add(target)
            links.append(target)

    internal_links = [
        link for link in links
        if urlparse(link).netloc == host
    ]
    external_links = [
        link for link in links
        if urlparse(link).netloc != host
    ]

    robots_url = urljoin(final_url, "/robots.txt")
    sitemap_url = urljoin(final_url, "/sitemap.xml")

    robots_status = resource_status(robots_url, timeout)
    sitemap_status = resource_status(sitemap_url, timeout)

    checks = [
        (
            "HTTPS",
            final_url.startswith("https://"),
            "Secure HTTPS connection detected."
        ),
        (
            "Title",
            10 <= len(title) <= 60,
            f"Current length: {len(title)} characters."
        ),
        (
            "Meta Description",
            50 <= len(description) <= 160,
            f"Current length: {len(description)} characters."
        ),
        (
            "Exactly One H1",
            len(h1) == 1,
            f"Found {len(h1)} H1 tag(s)."
        ),
        (
            "Image ALT Text",
            len(missing_alt) == 0,
            f"{len(missing_alt)} image(s) missing ALT text."
        ),
        (
            "Canonical",
            canonical is not None,
            "Canonical tag found." if canonical else "Canonical tag missing."
        ),
        (
            "Viewport",
            viewport is not None,
            "Viewport tag found." if viewport else "Viewport tag missing."
        ),
        (
            "Open Graph",
            bool(og_title and og_description),
            "OG title and description found."
            if og_title and og_description
            else "Open Graph data is incomplete."
        ),
        (
            "Robots.txt",
            robots_status == 200,
            f"HTTP status: {robots_status or 'unavailable'}."
        ),
        (
            "Sitemap.xml",
            sitemap_status == 200,
            f"HTTP status: {sitemap_status or 'unavailable'}."
        )
    ]

    category_items = {
        "Technical SEO": [checks[0], checks[5], checks[6], checks[8], checks[9]],
        "On-Page SEO": [checks[1], checks[2], checks[3]],
        "Images": [checks[4]],
        "Social/Mobile": [checks[7]]
    }

    scores = {}

    for category, items in category_items.items():
        scores[category] = round(
            sum(1 for _, passed, _ in items if passed)
            / len(items)
            * 100
        )

    link_results = []

    if run_link_checker and links:
        targets = links[:100]

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(check_link, link, min(timeout, 10))
                for link in targets
            ]

            for future in as_completed(futures):
                link_results.append(future.result())

    broken_links = [
        item for item in link_results
        if item["State"].startswith("Broken")
        or item["State"] == "Unreachable"
    ]

    redirects = [
        item for item in link_results
        if item["State"] == "Redirect"
    ]

    if link_results:
        link_score = round(
            (len(link_results) - len(broken_links))
            / len(link_results)
            * 100
        )
        scores["Links"] = link_score

    overall_score = round(sum(scores.values()) / len(scores))

    return {
        "response": response,
        "final_url": final_url,
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
        "links": links,
        "internal_links": internal_links,
        "external_links": external_links,
        "robots_status": robots_status,
        "sitemap_status": sitemap_status,
        "checks": checks,
        "scores": scores,
        "overall_score": overall_score,
        "link_results": link_results,
        "broken_links": broken_links,
        "redirects": redirects
    }

st.title("🔎 SEO Auditor Pro")
st.caption("Professional website SEO analysis • Development Build v3")

with st.sidebar:
    st.header("Audit Settings")
    timeout = st.slider(
        "Request timeout (seconds)",
        min_value=5,
        max_value=30,
        value=15
    )

    run_link_checker = st.checkbox(
        "Run Broken Link Checker",
        value=True
    )

    st.info(
        "Public demo checks up to 100 unique links per audit "
        "to keep the app responsive."
    )

website_url = st.text_input(
    "Website URL",
    placeholder="https://example.com"
)

if st.button("🚀 Run Full SEO Audit", type="primary"):

    if not website_url.strip():
        st.warning("Please enter a website URL.")

    else:
        try:
            with st.spinner(
                "Analyzing SEO, technical settings and links..."
            ):
                data = audit(
                    website_url,
                    timeout,
                    run_link_checker
                )

            st.success("Audit completed successfully.")

            col1, col2, col3, col4 = st.columns(4)

            col1.metric(
                "Overall Score",
                f"{data['overall_score']}/100"
            )
            col2.metric(
                "HTTP Status",
                data["response"].status_code
            )
            col3.metric(
                "Total Links",
                len(data["links"])
            )
            col4.metric(
                "Broken Links",
                len(data["broken_links"])
            )

            st.subheader("📊 SEO Scorecard")

            score_columns = st.columns(len(data["scores"]))

            for column, (name, score) in zip(
                score_columns,
                data["scores"].items()
            ):
                column.metric(name, f"{score}/100")
                column.progress(score / 100)

            st.subheader("🧾 Page Overview")

            st.write(
                "**Final URL:**",
                data["final_url"]
            )
            st.write(
                "**Title:**",
                data["title"] or "Missing"
            )
            st.write(
                "**Meta Description:**",
                data["description"] or "Missing"
            )
            st.write(
                "**H1:**",
                " | ".join(data["h1"])
                if data["h1"]
                else "Missing"
            )
            st.write(
                "**H2 count:**",
                len(data["h2"])
            )
            st.write(
                "**H3 count:**",
                len(data["h3"])
            )

            st.subheader("🔍 SEO Checks")

            check_rows = []

            for name, passed, detail in data["checks"]:
                check_rows.append({
                    "Check": name,
                    "Status": (
                        "✅ PASS"
                        if passed
                        else "❌ NEEDS WORK"
                    ),
                    "Details": detail
                })

            checks_df = pd.DataFrame(check_rows)

            st.dataframe(
                checks_df,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("🔗 Link Health")

            if data["link_results"]:

                a, b, c, d = st.columns(4)

                a.metric(
                    "Checked",
                    len(data["link_results"])
                )
                b.metric(
                    "Working",
                    len(data["link_results"])
                    - len(data["broken_links"])
                )
                c.metric(
                    "Broken / Unreachable",
                    len(data["broken_links"])
                )
                d.metric(
                    "Redirects",
                    len(data["redirects"])
                )

                link_df = pd.DataFrame(
                    data["link_results"]
                )

                st.dataframe(
                    link_df,
                    use_container_width=True,
                    hide_index=True
                )

                if data["broken_links"]:
                    st.error(
                        f"Found {len(data['broken_links'])} "
                        "broken or unreachable link(s)."
                    )
                else:
                    st.success(
                        "No broken links were detected "
                        "among the checked links."
                    )

            elif run_link_checker:
                st.info("No links were available to check.")

            else:
                st.info(
                    "Broken Link Checker is disabled."
                )

            st.subheader("🖼️ Image Analysis")

            st.write(
                f"Total images: **{len(data['images'])}**"
            )

            if data["missing_alt"]:
                st.error(
                    f"{len(data['missing_alt'])} image(s) "
                    "are missing ALT text."
                )
            else:
                st.success(
                    "All detected images have ALT text."
                )

            st.subheader("🧰 Technical Resources")

            a, b, c = st.columns(3)

            a.metric(
                "Robots.txt",
                "Found"
                if data["robots_status"] == 200
                else "Not found"
            )

            b.metric(
                "Sitemap.xml",
                "Found"
                if data["sitemap_status"] == 200
                else "Not found"
            )

            c.metric(
                "Canonical",
                "Found"
                if data["canonical"]
                else "Missing"
            )

            st.subheader("📣 Social / Mobile")

            a, b = st.columns(2)

            a.metric(
                "Viewport",
                "PASS"
                if data["viewport"]
                else "MISSING"
            )

            b.metric(
                "Open Graph",
                "PASS"
                if data["og_title"]
                and data["og_description"]
                else "INCOMPLETE"
            )

            st.subheader("💡 Recommendations")

            recommendations = []

            for name, passed, detail in data["checks"]:
                if not passed:
                    recommendations.append(
                        f"**{name}:** {detail}"
                    )

            if data["broken_links"]:
                recommendations.append(
                    f"**Broken Links:** Fix or remove "
                    f"{len(data['broken_links'])} "
                    "broken/unreachable link(s)."
                )

            if data["redirects"]:
                recommendations.append(
                    f"**Redirects:** Review "
                    f"{len(data['redirects'])} redirecting "
                    "link(s) for unnecessary hops."
                )

            if recommendations:
                for item in recommendations:
                    st.markdown("- " + item)
            else:
                st.success(
                    "No major issues were detected "
                    "by the current checks."
                )

            report_rows = check_rows.copy()

            if data["link_results"]:
                report_rows.append({
                    "Check": "Link Health",
                    "Status": (
                        "✅ PASS"
                        if not data["broken_links"]
                        else "❌ NEEDS WORK"
                    ),
                    "Details": (
                        f"Checked {len(data['link_results'])}; "
                        f"broken/unreachable: "
                        f"{len(data['broken_links'])}; "
                        f"redirects: {len(data['redirects'])}"
                    )
                })

            report_df = pd.DataFrame(report_rows)

            st.download_button(
                "⬇️ Download SEO Audit CSV",
                report_df.to_csv(index=False).encode("utf-8"),
                "seo_audit_v3.csv",
                "text/csv"
            )

        except requests.RequestException as exc:
            st.error(
                f"Could not access the website: {exc}"
            )

        except Exception as exc:
            st.error(
                f"Audit error: {exc}"
            )

st.divider()
st.caption("SEO Auditor Pro v3 • Development build")
