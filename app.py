

Haan 👍 ab screenshot se clear hai ke app properly live hai aur professional look bhi aa raha hai. Tumhara core product ready hai.

Lekin selling se pehle ek final polish zaroor karni chahiye:

🔴 Abhi jo cheez change karni hai
Header mein:

Professional Website SEO Analysis • Development Build v5

selling version mein Development Build v5 nahi hona chahiye.

Isko simply:

Professional Website SEO Analysis

karna better hai.

Aur footer:

SEO Auditor Pro v5 • Development build

ko:

SEO Auditor Pro • Professional Website SEO Analysis

kar denge.

🟢 Baaki current features keep karo
Full SEO audit ✅

SEO scorecard ✅

Broken link checker ✅

Redirect detection ✅

Website crawler ✅

Multiple H1 detection ✅

Missing meta detection ✅

Canonical check ✅

Sitemap check ✅

Robots.txt check ✅

Open Graph check ✅

Image ALT check ✅

CSV export ✅

Ab iske baad features add karte rehna zaroori nahi. Product ko unnecessarily complicated karne se bugs aur rejection ka risk badhega.

🎯 Final workflow
Current live app → final branding polish → screenshots → documentation → marketplace package → listing.

Agar tum chaho to main abhi final selling version ka app.py bana deta hoon, jisme sirf Development Build v5 wali branding remove hogi aur UI ko marketplace-ready polish milegi.


kar do jo karna hai jo kah rahe ho

Done ✅ Final selling version ready hai. Maine working v5 ki functionality ko preserve karke marketplace-facing branding polish kar di hai.

Final files





Complete package

Maine kya change kiya
❌ Development Build v5 remove

❌ Development build footer remove

✅ Clean Professional Website SEO Analysis branding

✅ Sidebar ko product-style polish

✅ Features clearly listed

✅ Installation documentation

✅ Streamlit deployment instructions

✅ Product scope/limitations

✅ Release checklist

✅ Marketplace package ready

Ab GitHub ke liye app.py + requirements.txt upload karo. ZIP ko GitHub mein upload karne ki zaroorat nahi—ZIP sirf final marketplace package ke liye hai.

Tumhara existing Streamlit URL isi code ke saath update/redeploy kar dena.




2 more

48110aac-cab2-400b-b7d9-d9a2bb505c0f.png

Haan, error samajh aa gaya. ⚠️

Ye code ka error nahi hai. Screenshot mein clearly hai:

app.py, line 2
0d929c64-...png
SyntaxError: invalid decimal literal

Matlab GitHub mein app.py ke andar galti se PNG/image file ka naam/code paste ho gaya hai. Isliye Python usko code samajh kar error de raha hai.

Maine apni final app.py ko check bhi kiya — Python compile successfully ho raha hai. ✅

Ab ye karo — sirf ek baar
GitHub mein:

Repository kholo.

app.py kholo.

Pura purana content delete karo.

Ye clean file upload karo:


GitHub mein Commit changes karo.

Streamlit automatically redeploy hone do.

Important
PNG ko app.py mein bilkul mat daalna.
Agar screenshot upload karni hai to uska naam screenshots/ folder mein rakho.

Aur agar tum complete package rakhna chahte ho:


Is package ki app.py maine compile karke verify ki hai. ✅

Abhi sirf app.py replace karo. Baaki working v5 code ko touch mat karo. 



Library
/
app.py


import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque

st.set_page_config(page_title="SEO Auditor Pro", page_icon="🔎", layout="wide", initial_sidebar_state="expanded")

UA = "SEO-Auditor-Pro/5.0"

def normalize_url(url):
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "https://" + url

def same_site(a, b):
    return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()

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
        if r.status_code in (403, 405) or r.status_code >= 500:
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
            "URL": url, "Status": status, "State": state,
            "Redirects": redirects, "Final URL": final_url, "Error": ""
        }
    except requests.RequestException as exc:
        return {
            "URL": url, "Status": None, "State": "Unreachable",
            "Redirects": 0, "Final URL": "", "Error": str(exc)
        }

def resource_status(url, timeout):
    try:
        return fetch(url, min(timeout, 10), "GET").status_code
    except requests.RequestException:
        return None

def page_checks(soup, final_url):
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    description = desc_tag.get("content", "").strip() if desc_tag else ""

    h1 = [x.get_text(" ", strip=True) for x in soup.find_all("h1")]
    h2 = [x.get_text(" ", strip=True) for x in soup.find_all("h2")]
    h3 = [x.get_text(" ", strip=True) for x in soup.find_all("h3")]

    images = soup.find_all("img")
    missing_alt = [img.get("src", "") for img in images if not img.get("alt", "").strip()]

    canonical = soup.find("link", rel=lambda value: value and "canonical" in value)
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    og_title = soup.find("meta", property="og:title")
    og_description = soup.find("meta", property="og:description")

    title_ok = 10 <= len(title) <= 60
    meta_ok = 50 <= len(description) <= 160
    h1_status = "PASS" if len(h1) == 1 else ("WARNING" if len(h1) > 1 else "ERROR")

    checks = [
        ("HTTPS", final_url.startswith("https://"), "Secure HTTPS connection detected."),
        ("Title", title_ok, f"Current length: {len(title)} characters."),
        ("Meta Description", meta_ok, f"Current length: {len(description)} characters."),
        ("H1 Structure", h1_status == "PASS", f"Found {len(h1)} H1 tag(s). {h1_status}."),
        ("Image ALT Text", len(images) == 0 or len(missing_alt) == 0,
         "No images found (N/A)." if len(images) == 0 else f"{len(missing_alt)} image(s) missing ALT text."),
        ("Canonical", canonical is not None, "Canonical tag found." if canonical else "Canonical tag missing."),
        ("Viewport", viewport is not None, "Viewport tag found." if viewport else "Viewport tag missing."),
        ("Open Graph", bool(og_title and og_description),
         "OG title and description found." if og_title and og_description else "Open Graph data is incomplete."),
    ]

    return {
        "title": title, "description": description, "h1": h1, "h2": h2, "h3": h3,
        "images": images, "missing_alt": missing_alt, "canonical": canonical,
        "viewport": viewport, "og_title": og_title, "og_description": og_description,
        "checks": checks
    }

def crawl_site(start_url, max_pages, timeout):
    start_url = normalize_url(start_url)
    queue = deque([start_url])
    queued = {start_url}
    visited = set()
    pages = []
    progress = st.progress(0, text="Crawling website...")

    while queue and len(visited) < max_pages:
        current = queue.popleft()
        if current in visited:
            continue

        try:
            response = fetch(current, timeout, "GET")
            final_url = response.url
            if not same_site(start_url, final_url):
                visited.add(current)
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            info = page_checks(soup, final_url)

            pages.append({
                "URL": final_url,
                "Status": response.status_code,
                "Title": info["title"],
                "Meta Description": info["description"],
                "H1 Count": len(info["h1"]),
                "H2 Count": len(info["h2"]),
                "Images": len(info["images"]),
                "Missing ALT": len(info["missing_alt"]),
                "Canonical": "Yes" if info["canonical"] else "No",
            })
            visited.add(current)

            for a in soup.find_all("a", href=True):
                target = urljoin(final_url, a["href"]).split("#")[0]
                parsed = urlparse(target)
                if parsed.scheme in ("http", "https") and same_site(start_url, target):
                    if target not in queued and len(queued) < max_pages * 3:
                        queued.add(target)
                        queue.append(target)

        except requests.RequestException:
            visited.add(current)
        except Exception:
            visited.add(current)

        progress.progress(
            min(len(visited) / max_pages, 1.0),
            text=f"Crawling pages: {len(visited)}/{max_pages}"
        )

    progress.empty()
    return pages

def calculate_scores(checks, link_results, image_count):
    def passed(name):
        return next(ok for n, ok, _ in checks if n == name)

    technical_items = [
        passed("HTTPS"), passed("Canonical"), passed("Viewport")
    ]
    onpage_items = [
        passed("Title"), passed("Meta Description"), passed("H1 Structure")
    ]
    social_items = [passed("Viewport"), passed("Open Graph")]

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
        "Social/Mobile": social
    }

    if link_results:
        broken = sum(
            1 for x in link_results
            if x["State"].startswith("Broken") or x["State"] == "Unreachable"
        )
        scores["Links"] = round((len(link_results) - broken) / len(link_results) * 100)

    weights = {
        "Technical SEO": 0.30,
        "On-Page SEO": 0.30,
        "Images": 0.10,
        "Social/Mobile": 0.10,
        "Links": 0.20
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

st.title("🔎 SEO Auditor Pro")
st.caption("Professional Website SEO Analysis")

with st.sidebar:
    st.header("Audit Settings")

    timeout = st.slider("Request timeout (seconds)", 5, 30, 15)

    run_links = st.checkbox(
        "Run Full Broken Link Checker",
        value=True
    )

    run_crawler = st.checkbox(
        "Crawl Website Pages",
        value=True
    )

    max_pages = st.slider(
        "Maximum pages to crawl",
        min_value=1,
        max_value=50,
        value=10
    )

    st.info(
        "Analyze on-page SEO, technical signals, links, images, social/mobile data, "
        "and crawl same-domain pages from one dashboard."
    )

    st.markdown("---")
    st.markdown("**Included features**")
    st.caption(
        "SEO scorecard • Broken-link checker • Redirect detection • "
        "Website crawler • CSV report"
    )

website_url = st.text_input(
    "Website URL",
    placeholder="https://example.com"
)

if st.button("🚀 Run Complete Website Audit", type="primary"):
    if not website_url.strip():
        st.warning("Please enter a website URL.")
    else:
        try:
            with st.spinner("Running complete audit..."):
                first_response = fetch(normalize_url(website_url), timeout, "GET")
                soup = BeautifulSoup(first_response.text, "html.parser")
                final_url = first_response.url
                info = page_checks(soup, final_url)

                links = []
                seen = set()

                for a in soup.find_all("a", href=True):
                    target = urljoin(final_url, a["href"]).split("#")[0]
                    parsed = urlparse(target)
                    if parsed.scheme in ("http", "https") and target not in seen:
                        seen.add(target)
                        links.append(target)

                link_results = []

                if run_links and links:
                    progress = st.progress(0, text="Checking all page links...")
                    with ThreadPoolExecutor(max_workers=12) as executor:
                        futures = [
                            executor.submit(check_link, link, min(timeout, 10))
                            for link in links
                        ]
                        total = len(futures)
                        for i, future in enumerate(as_completed(futures), 1):
                            link_results.append(future.result())
                            progress.progress(i / total, text=f"Checking links: {i}/{total}")
                    progress.empty()

                robots = resource_status(urljoin(final_url, "/robots.txt"), timeout)
                sitemap = resource_status(urljoin(final_url, "/sitemap.xml"), timeout)

                info["checks"].extend([
                    ("Robots.txt", robots == 200, f"HTTP status: {robots or 'unavailable'}."),
                    ("Sitemap.xml", sitemap == 200, f"HTTP status: {sitemap or 'unavailable'}.")
                ])

                scores, overall = calculate_scores(
                    info["checks"][:8],
                    link_results,
                    len(info["images"])
                )

                if run_crawler:
                    crawl_pages = crawl_site(
                        final_url,
                        max_pages,
                        timeout
                    )
                else:
                    crawl_pages = []

            st.success("Complete audit finished successfully.")

            broken = [
                x for x in link_results
                if x["State"].startswith("Broken")
                or x["State"] == "Unreachable"
            ]
            redirects = [x for x in link_results if x["Redirects"] > 0]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Overall SEO", f"{overall}/100")
            c2.metric("HTTP Status", first_response.status_code)
            c3.metric("Total Links", len(links))
            c4.metric("Broken Links", len(broken))

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
                st.success("Excellent SEO foundation.")
            elif overall >= 60:
                st.warning("Good foundation with several improvements recommended.")
            else:
                st.error("Major SEO improvements are recommended.")

            st.subheader("🧾 Page Overview")
            st.write("**Final URL:**", final_url)
            st.write("**Title:**", info["title"] or "Missing")
            st.write("**Meta Description:**", info["description"] or "Missing")
            st.write("**H1:**", " | ".join(info["h1"]) if info["h1"] else "Missing")
            st.write("**H1 count:**", len(info["h1"]))
            st.write("**H2 count:**", len(info["h2"]))
            st.write("**H3 count:**", len(info["h3"]))

            st.subheader("🔍 SEO Checks")

            check_rows = []
            for name, passed, detail in info["checks"]:
                check_rows.append({
                    "Check": name,
                    "Status": "✅ PASS" if passed else "⚠️ NEEDS WORK",
                    "Details": detail
                })

            st.dataframe(
                pd.DataFrame(check_rows),
                use_container_width=True,
                hide_index=True
            )

            st.subheader("🔗 Full Link Health")

            if link_results:
                a, b, c, d = st.columns(4)
                a.metric("Checked", len(link_results))
                b.metric("Working", len(link_results) - len(broken))
                c.metric("Broken / Unreachable", len(broken))
                d.metric("Redirecting", len(redirects))

                link_df = pd.DataFrame(link_results)
                st.dataframe(
                    link_df,
                    use_container_width=True,
                    hide_index=True
                )

                if broken:
                    st.markdown("### ❌ Broken Links Only")
                    st.dataframe(
                        pd.DataFrame(broken),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("No broken or unreachable links detected.")

            st.subheader("🖼️ Image Analysis")
            st.write(f"Total images: **{len(info['images'])}**")

            if len(info["images"]) == 0:
                st.info("No images detected — Image SEO score is N/A.")
            elif info["missing_alt"]:
                st.error(
                    f"{len(info['missing_alt'])} image(s) are missing ALT text."
                )
            else:
                st.success("All detected images have ALT text.")

            st.subheader("🧰 Technical Resources")
            a, b, c = st.columns(3)
            a.metric("Robots.txt", "Found" if robots == 200 else "Not found")
            b.metric("Sitemap.xml", "Found" if sitemap == 200 else "Not found")
            c.metric("Canonical", "Found" if info["canonical"] else "Missing")

            if run_crawler:
                st.subheader("🕷️ Website Crawl")
                st.write(
                    f"Pages discovered/crawled: **{len(crawl_pages)}** "
                    f"(maximum set to {max_pages})"
                )

                if crawl_pages:
                    crawl_df = pd.DataFrame(crawl_pages)
                    st.dataframe(
                        crawl_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    missing_meta_pages = crawl_df[
                        crawl_df["Meta Description"].fillna("").eq("")
                    ]
                    multiple_h1 = crawl_df[crawl_df["H1 Count"] > 1]
                    no_h1 = crawl_df[crawl_df["H1 Count"] == 0]

                    a, b, c = st.columns(3)
                    a.metric("Missing Meta", len(missing_meta_pages))
                    b.metric("Multiple H1", len(multiple_h1))
                    c.metric("Missing H1", len(no_h1))

            st.subheader("📣 Social / Mobile")
            a, b = st.columns(2)
            a.metric("Viewport", "PASS" if info["viewport"] else "MISSING")
            b.metric(
                "Open Graph",
                "PASS" if info["og_title"] and info["og_description"]
                else "INCOMPLETE"
            )

            st.subheader("💡 Recommendations")

            recommendations = []

            for name, passed, detail in info["checks"]:
                if not passed:
                    if name == "H1 Structure" and len(info["h1"]) > 1:
                        recommendations.append(
                            f"**H1 Structure:** Found {len(info['h1'])} H1 tags. "
                            "Use one primary H1 and move other headings to H2/H3 where appropriate."
                        )
                    else:
                        recommendations.append(f"**{name}:** {detail}")

            if broken:
                recommendations.append(
                    f"**Broken Links:** Fix {len(broken)} broken/unreachable link(s)."
                )

            if redirects:
                recommendations.append(
                    f"**Redirects:** Review {len(redirects)} redirecting link(s) "
                    "and remove unnecessary redirect chains."
                )

            if crawl_pages:
                missing_meta_count = sum(
                    not row["Meta Description"]
                    for row in crawl_pages
                )
                if missing_meta_count:
                    recommendations.append(
                        f"**Crawl:** {missing_meta_count} crawled page(s) "
                        "have no meta description."
                    )

            if recommendations:
                for recommendation in recommendations:
                    st.markdown("- " + recommendation)
            else:
                st.success("No major issues detected.")

            report_rows = check_rows.copy()
            report_rows.extend([
                {
                    "Check": "Overall SEO Score",
                    "Status": f"{overall}/100",
                    "Details": "Weighted score excluding unavailable categories."
                },
                {
                    "Check": "Broken Links",
                    "Status": "PASS" if not broken else "NEEDS WORK",
                    "Details": f"Checked {len(link_results)}; broken/unreachable {len(broken)}."
                },
                {
                    "Check": "Redirects",
                    "Status": "INFO",
                    "Details": f"{len(redirects)} redirecting link(s) detected."
                }
            ])

            report_df = pd.DataFrame(report_rows)

            st.download_button(
                "⬇️ Download SEO Audit CSV",
                report_df.to_csv(index=False).encode("utf-8"),
                "seo_audit_v5.csv",
                "text/csv"
            )

        except requests.RequestException as exc:
            st.error(f"Could not access the website: {exc}")
        except Exception as exc:
            st.error(f"Audit error: {exc}")

st.divider()
st.caption("SEO Auditor Pro • Professional Website SEO Analysis")
