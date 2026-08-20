import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="SEO Auditor Pro", page_icon="🔎", layout="wide")

UA = "SEO-Auditor-Pro/1.0 (+https://streamlit.io)"

def fetch(url, timeout=15):
    headers = {"User-Agent": UA}
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

def audit(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    r = fetch(url)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    desc = desc_tag.get("content", "").strip() if desc_tag else ""

    h1s = [x.get_text(" ", strip=True) for x in soup.find_all("h1")]
    h2s = [x.get_text(" ", strip=True) for x in soup.find_all("h2")]
    images = soup.find_all("img")
    missing_alt = [img.get("src", "") for img in images if not img.get("alt", "").strip()]

    links = []
    for a in soup.find_all("a", href=True):
        href = urljoin(r.url, a["href"])
        p = urlparse(href)
        if p.scheme in ("http", "https"):
            links.append(href)

    canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
    robots_url = urljoin(r.url, "/robots.txt")
    sitemap_url = urljoin(r.url, "/sitemap.xml")

    checks = [
        ("HTTPS", r.url.startswith("https://"), "Use HTTPS for the audited page."),
        ("Title", 10 <= len(title) <= 60, f"Title length: {len(title)}"),
        ("Meta Description", 50 <= len(desc) <= 160, f"Description length: {len(desc)}"),
        ("H1", len(h1s) == 1, f"Found {len(h1s)} H1 tag(s)."),
        ("Images ALT", len(images) == 0 or len(missing_alt) == 0,
         f"{len(missing_alt)} image(s) missing ALT text."),
        ("Canonical", canonical is not None, "Canonical link found." if canonical else "Canonical link missing."),
        ("Robots.txt", None, robots_url),
        ("Sitemap", None, sitemap_url),
    ]

    scoreable = [c for c in checks if c[1] is not None]
    score = round(sum(bool(c[1]) for c in scoreable) / len(scoreable) * 100) if scoreable else 0

    return {
        "url": r.url,
        "status": r.status_code,
        "score": score,
        "title": title,
        "description": desc,
        "h1s": h1s,
        "h2s": h2s,
        "images": len(images),
        "missing_alt": len(missing_alt),
        "links": len(links),
        "canonical": canonical.get("href") if canonical else "",
        "robots_url": robots_url,
        "sitemap_url": sitemap_url,
        "checks": checks,
    }

st.title("🔎 SEO Auditor Pro")
st.caption("Python + Streamlit website SEO analysis demo")

with st.sidebar:
    st.header("Audit Settings")
    timeout = st.slider("Request timeout (seconds)", 5, 30, 15)
    st.info("Demo version: audits one public URL at a time.")

url = st.text_input("Website URL", placeholder="https://example.com")

if st.button("🚀 Run SEO Audit", type="primary"):
    if not url.strip():
        st.warning("Please enter a website URL.")
    else:
        try:
            with st.spinner("Analyzing website..."):
                data = audit(url.strip())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("SEO Score", f"{data['score']}/100")
            c2.metric("HTTP Status", data["status"])
            c3.metric("Images", data["images"])
            c4.metric("Links", data["links"])

            st.subheader("Page Overview")
            st.write("**Final URL:**", data["url"])
            st.write("**Title:**", data["title"] or "Missing")
            st.write("**Meta Description:**", data["description"] or "Missing")
            st.write("**H1:**", " | ".join(data["h1s"]) if data["h1s"] else "Missing")
            st.write("**H2 count:**", len(data["h2s"]))
            st.write("**Missing ALT images:**", data["missing_alt"])

            st.subheader("SEO Checks")
            rows = []
            for name, passed, detail in data["checks"]:
                if passed is None:
                    status = "ℹ️"
                else:
                    status = "✅ Pass" if passed else "❌ Needs work"
                rows.append({"Check": name, "Status": status, "Details": detail})
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Audit CSV",
                data=csv,
                file_name="seo_audit_report.csv",
                mime="text/csv"
            )

        except requests.RequestException as e:
            st.error(f"Could not access the website: {e}")
        except Exception as e:
            st.error(f"Audit error: {e}")

st.divider()
st.caption("SEO Auditor Pro • Development build")
