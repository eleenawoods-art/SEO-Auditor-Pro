import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

st.set_page_config(page_title="SEO Auditor Pro", page_icon="🔎", layout="wide")

UA = "SEO-Auditor-Pro/4.0"

def normalize_url(url):
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "https://" + url

def fetch(url, timeout=15, method="GET"):
    return requests.request(
        method,
        url,
        headers={"User-Agent": UA},
        timeout=timeout,
        allow_redirects=True
    )

def check_link(url, timeout):
    try:
        r = fetch(url, timeout, "HEAD")
        # Some servers reject HEAD. Fall back to GET.
        if r.status_code in (405, 403) or r.status_code >= 500:
            r = fetch(url, timeout, "GET")

        status = r.status_code
        final_url = r.url
        redirects = len(r.history)

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
            "Error": ""
        }
    except requests.RequestException as exc:
        return {
            "URL": url,
            "Status": None,
            "State": "Unreachable",
            "Redirects": 0,
            "Final URL": "",
            "Error": str(exc)
        }

def resource_status(url, timeout):
    try:
        r = fetch(url, min(timeout, 10), "GET")
        return r.status_code
    except requests.RequestException:
        return None

def score_group(items):
    return round(sum(1 for _, passed, _ in items if passed) / len(items) * 100)

def audit(url, timeout, run_links):
    response = fetch(normalize_url(url), timeout, "GET")
    soup = BeautifulSoup(response.text, "html.parser")
    final_url = response.url
    host = urlparse(final_url).netloc

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
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

    internal = [u for u in links if urlparse(u).netloc == host]
    external = [u for u in links if urlparse(u).netloc != host]

    robots_status = resource_status(
        urljoin(final_url, "/robots.txt"), timeout
    )
    sitemap_status = resource_status(
        urljoin(final_url, "/sitemap.xml"), timeout
    )

    checks = [
        ("HTTPS", final_url.startswith("https://"),
         "Secure HTTPS connection detected."),
        ("Title", 10 <= len(title) <= 60,
         f"Current length: {len(title)} characters."),
        ("Meta Description", 50 <= len(description) <= 160,
         f"Current length: {len(description)} characters."),
        ("Exactly One H1", len(h1) == 1,
         f"Found {len(h1)} H1 tag(s)."),
        ("Image ALT Text", len(missing_alt) == 0,
         f"{len(missing_alt)} image(s) missing ALT text."),
        ("Canonical", canonical is not None,
         "Canonical tag found." if canonical else "Canonical tag missing."),
        ("Viewport", viewport is not None,
         "Viewport tag found." if viewport else "Viewport tag missing."),
        ("Open Graph", bool(og_title and og_description),
         "OG title and description found."
         if og_title and og_description
         else "Open Graph data is incomplete."),
        ("Robots.txt", robots_status == 200,
         f"HTTP status: {robots_status or 'unavailable'}."),
        ("Sitemap.xml", sitemap_status == 200,
         f"HTTP status: {sitemap_status or 'unavailable'}.")
    ]

    groups = {
        "Technical SEO": [checks[0], checks[5], checks[6], checks[8], checks[9]],
        "On-Page SEO": [checks[1], checks[2], checks[3]],
        "Images": [checks[4]],
        "Social/Mobile": [checks[7]]
    }

    scores = {name: score_group(items) for name, items in groups.items()}

    link_results = []

    if run_links and links:
        # Full scan: every discovered HTTP/HTTPS link.
        progress = st.progress(0, text="Checking all discovered links...")
        total = len(links)

        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = {
                executor.submit(check_link, link, min(timeout, 10)): link
                for link in links
            }

            completed = 0
            for future in as_completed(futures):
                link_results.append(future.result())
                completed += 1
                progress.progress(
                    completed / total,
                    text=f"Checking links: {completed}/{total}"
                )

        progress.empty()

    broken = [
        x for x in link_results
        if x["State"].startswith("Broken")
        or x["State"] == "Unreachable"
    ]
    redirects = [x for x in link_results if x["Redirects"] > 0]

    if link_results:
        link_score = round(
            (len(link_results) - len(broken))
            / len(link_results)
            * 100
        )
        scores["Links"] = link_score

    # Weighted overall score. Links are useful but should not dominate.
    weights = {
        "Technical SEO": 0.30,
        "On-Page SEO": 0.30,
        "Images": 0.10,
        "Social/Mobile": 0.10,
        "Links": 0.20
    }

    available_weights = {
        k: v for k, v in weights.items() if k in scores
    }
    total_weight = sum(available_weights.values())

    overall = round(
        sum(scores[k] * available_weights[k] for k in available_weights)
        / total_weight
    )

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
        "internal": internal,
        "external": external,
        "robots_status": robots_status,
        "sitemap_status": sitemap_status,
        "checks": checks,
        "scores": scores,
        "overall": overall,
        "link_results": link_results,
        "broken": broken,
        "redirects": redirects
    }

st.title("🔎 SEO Auditor Pro")
st.caption("Professional Website SEO Analysis • Development Build v4")

with st.sidebar:
    st.header("Audit Settings")

    timeout = st.slider(
        "Request timeout (seconds)",
        5, 30, 15
    )

    run_links = st.checkbox(
        "Run Full Broken Link Checker",
        value=True
    )

    st.success(
        "v4 scans every discovered HTTP/HTTPS link on the audited page."
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
            with st.spinner("Starting complete SEO audit..."):
                data = audit(
                    website_url,
                    timeout,
                    run_links
                )

            st.success("Full audit completed successfully.")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Overall SEO", f"{data['overall']}/100")
            c2.metric("HTTP Status", data["response"].status_code)
            c3.metric("Total Links", len(data["links"]))
            c4.metric("Broken Links", len(data["broken"]))

            st.subheader("📊 Professional SEO Scorecard")

            score_cols = st.columns(len(data["scores"]))
            for col, (name, value) in zip(
                score_cols,
                data["scores"].items()
            ):
                col.metric(name, f"{value}/100")
                col.progress(value / 100)

            if data["overall"] >= 80:
                st.success("Excellent SEO foundation.")
            elif data["overall"] >= 60:
                st.warning("Good foundation with several improvements recommended.")
            else:
                st.error("Major SEO improvements are recommended.")

            st.subheader("🧾 Page Overview")

            st.write("**Final URL:**", data["final_url"])
            st.write("**Title:**", data["title"] or "Missing")
            st.write("**Meta Description:**", data["description"] or "Missing")
            st.write(
                "**H1:**",
                " | ".join(data["h1"]) if data["h1"] else "Missing"
            )
            st.write("**H2 count:**", len(data["h2"]))
            st.write("**H3 count:**", len(data["h3"]))

            st.subheader("🔍 SEO Checks")

            check_rows = [
                {
                    "Check": name,
                    "Status": "✅ PASS" if passed else "❌ NEEDS WORK",
                    "Details": detail
                }
                for name, passed, detail in data["checks"]
            ]

            checks_df = pd.DataFrame(check_rows)

            st.dataframe(
                checks_df,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("🔗 Full Link Health")

            if data["link_results"]:
                a, b, c, d = st.columns(4)

                a.metric("Checked", len(data["link_results"]))
                b.metric(
                    "Working",
                    len(data["link_results"]) - len(data["broken"])
                )
                c.metric("Broken / Unreachable", len(data["broken"]))
                d.metric("Redirecting", len(data["redirects"]))

                link_df = pd.DataFrame(data["link_results"])

                st.dataframe(
                    link_df,
                    use_container_width=True,
                    hide_index=True
                )

                if data["broken"]:
                    st.error(
                        f"{len(data['broken'])} broken or unreachable "
                        "link(s) found."
                    )

                    broken_df = pd.DataFrame(data["broken"])
                    st.markdown("### ❌ Broken Links Only")
                    st.dataframe(
                        broken_df,
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success(
                        "No broken or unreachable links were detected."
                    )
            else:
                st.info("Link checker was disabled or no links were found.")

            st.subheader("🖼️ Image Analysis")

            st.write(f"Total images: **{len(data['images'])}**")

            if data["missing_alt"]:
                st.error(
                    f"{len(data['missing_alt'])} image(s) are missing ALT text."
                )
            else:
                st.success("All detected images have ALT text.")

            st.subheader("🧰 Technical Resources")

            a, b, c = st.columns(3)

            a.metric(
                "Robots.txt",
                "Found" if data["robots_status"] == 200 else "Not found"
            )
            b.metric(
                "Sitemap.xml",
                "Found" if data["sitemap_status"] == 200 else "Not found"
            )
            c.metric(
                "Canonical",
                "Found" if data["canonical"] else "Missing"
            )

            st.subheader("📣 Social / Mobile")

            a, b = st.columns(2)

            a.metric(
                "Viewport",
                "PASS" if data["viewport"] else "MISSING"
            )
            b.metric(
                "Open Graph",
                "PASS"
                if data["og_title"] and data["og_description"]
                else "INCOMPLETE"
            )

            st.subheader("💡 Recommendations")

            recommendations = []

            for name, passed, detail in data["checks"]:
                if not passed:
                    recommendations.append(
                        f"**{name}:** {detail}"
                    )

            if data["broken"]:
                recommendations.append(
                    f"**Broken Links:** Fix or remove "
                    f"{len(data['broken'])} broken/unreachable link(s)."
                )

            if data["redirects"]:
                recommendations.append(
                    f"**Redirects:** Review "
                    f"{len(data['redirects'])} redirecting link(s)."
                )

            if recommendations:
                for recommendation in recommendations:
                    st.markdown("- " + recommendation)
            else:
                st.success("No major issues detected by current checks.")

            report_rows = check_rows.copy()

            report_rows.append({
                "Check": "Overall SEO Score",
                "Status": f"{data['overall']}/100",
                "Details": "Weighted professional score"
            })

            report_rows.append({
                "Check": "Link Health",
                "Status": (
                    "PASS"
                    if not data["broken"]
                    else "NEEDS WORK"
                ),
                "Details": (
                    f"Checked {len(data['link_results'])}; "
                    f"broken/unreachable {len(data['broken'])}; "
                    f"redirecting {len(data['redirects'])}"
                )
            })

            report_df = pd.DataFrame(report_rows)

            st.download_button(
                "⬇️ Download SEO Audit CSV",
                report_df.to_csv(index=False).encode("utf-8"),
                "seo_audit_v4.csv",
                "text/csv"
            )

        except requests.RequestException as exc:
            st.error(f"Could not access the website: {exc}")

        except Exception as exc:
            st.error(f"Audit error: {exc}")

st.divider()
st.caption("SEO Auditor Pro v4 • Development build")
