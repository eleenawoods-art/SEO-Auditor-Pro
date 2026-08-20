import streamlit as st
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
from collections import Counter

st.set_page_config(page_title="SEO Auditor Pro", page_icon="🔎", layout="wide")
UA = "SEO-Auditor-Pro/2.0"

def normalize(url):
    url = url.strip()
    return url if url.startswith(("http://","https://")) else "https://" + url

def get(url, timeout):
    return requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)

def resource_status(url, timeout=10):
    try:
        r = get(url, timeout)
        return r.status_code
    except requests.RequestException:
        return None

def audit(url, timeout):
    r = get(normalize(url), timeout)
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    m = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    desc = m.get("content","").strip() if m else ""
    h1 = [x.get_text(" ",strip=True) for x in soup.find_all("h1")]
    h2 = [x.get_text(" ",strip=True) for x in soup.find_all("h2")]
    h3 = [x.get_text(" ",strip=True) for x in soup.find_all("h3")]
    imgs = soup.find_all("img")
    missing_alt = [x.get("src","") for x in imgs if not x.get("alt","").strip()]
    canonical = soup.find("link", rel=lambda x: x and "canonical" in x)
    viewport = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    ogt = soup.find("meta", property="og:title")
    ogd = soup.find("meta", property="og:description")
    host = urlparse(r.url).netloc
    internal, external = [], []
    for a in soup.find_all("a", href=True):
        u = urljoin(r.url, a["href"])
        if urlparse(u).scheme not in ("http","https"): continue
        (internal if urlparse(u).netloc == host else external).append(u)
    robots = resource_status(urljoin(r.url,"/robots.txt"))
    sitemap = resource_status(urljoin(r.url,"/sitemap.xml"))
    checks = [
        ("HTTPS", r.url.startswith("https://"), "Use HTTPS."),
        ("Title", 10 <= len(title) <= 60, f"Length: {len(title)} characters."),
        ("Meta Description", 50 <= len(desc) <= 160, f"Length: {len(desc)} characters."),
        ("Exactly One H1", len(h1)==1, f"Found {len(h1)} H1 tag(s)."),
        ("Image ALT Text", not missing_alt, f"{len(missing_alt)} image(s) missing ALT."),
        ("Canonical", canonical is not None, "Canonical tag found." if canonical else "Canonical tag missing."),
        ("Viewport", viewport is not None, "Viewport tag found." if viewport else "Viewport tag missing."),
        ("Open Graph", bool(ogt and ogd), "OG title/description found." if ogt and ogd else "OG data incomplete."),
        ("Robots.txt", robots == 200, f"HTTP: {robots or 'unavailable'}"),
        ("Sitemap.xml", sitemap == 200, f"HTTP: {sitemap or 'unavailable'}"),
    ]
    weights = {"HTTPS":15,"Title":12,"Meta Description":12,"Exactly One H1":10,"Image ALT Text":10,
               "Canonical":8,"Viewport":8,"Open Graph":5,"Robots.txt":10,"Sitemap.xml":10}
    score = sum(weights[n] for n,p,_ in checks if p)
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", soup.get_text(" ",strip=True).lower())
    return locals()

st.title("🔎 SEO Auditor Pro")
st.caption("Professional website SEO analysis • Development Build v2")

with st.sidebar:
    st.header("Audit Settings")
    timeout = st.slider("Request timeout (seconds)", 5, 30, 15)
    st.info("v2: technical SEO, links, images, social/mobile and resources.")

url = st.text_input("Website URL", placeholder="https://example.com")

if st.button("🚀 Run Complete SEO Audit", type="primary"):
    if not url.strip():
        st.warning("Please enter a website URL.")
    else:
        try:
            with st.spinner("Running complete SEO audit..."):
                d = audit(url, timeout)
            st.success("Audit completed successfully.")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("SEO Score", f"{d['score']}/100")
            c2.metric("HTTP Status", d["r"].status_code)
            c3.metric("Internal Links", len(d["internal"]))
            c4.metric("External Links", len(d["external"]))

            st.subheader("📊 SEO Health")
            st.progress(d["score"]/100)
            if d["score"] >= 80: st.success("Strong SEO foundation.")
            elif d["score"] >= 60: st.warning("Good foundation, but improvements are recommended.")
            else: st.error("Several important SEO improvements are recommended.")

            st.subheader("🧾 Page Overview")
            st.write("**Final URL:**", d["r"].url)
            st.write("**Title:**", d["title"] or "Missing")
            st.write("**Meta Description:**", d["desc"] or "Missing")
            st.write("**H1:**", " | ".join(d["h1"]) if d["h1"] else "Missing")
            st.write("**H2 count:**", len(d["h2"]))
            st.write("**H3 count:**", len(d["h3"]))

            rows=[]
            for n,p,detail in d["checks"]:
                rows.append({"Check":n,"Status":"✅ PASS" if p else "❌ NEEDS WORK","Details":detail})
            df=pd.DataFrame(rows)
            st.subheader("🔍 SEO Checks")
            st.dataframe(df,use_container_width=True,hide_index=True)

            st.subheader("🔗 Link Analysis")
            st.dataframe(pd.DataFrame({"Type":["Internal","External"],"Count":[len(d["internal"]),len(d["external"])]}),
                         use_container_width=True,hide_index=True)

            st.subheader("🖼️ Image Analysis")
            st.write(f"Total images: **{len(d['imgs'])}**")
            if d["missing_alt"]: st.error(f"{len(d['missing_alt'])} image(s) missing ALT text.")
            else: st.success("All detected images have ALT text.")

            st.subheader("🧰 Technical Resources")
            a,b,c=st.columns(3)
            a.metric("Robots.txt","Found" if d["robots"]==200 else "Not found")
            b.metric("Sitemap.xml","Found" if d["sitemap"]==200 else "Not found")
            c.metric("Canonical","Found" if d["canonical"] else "Missing")

            st.subheader("📣 Social / Mobile")
            a,b=st.columns(2)
            a.metric("Viewport","PASS" if d["viewport"] else "MISSING")
            b.metric("Open Graph","PASS" if d["ogt"] and d["ogd"] else "INCOMPLETE")

            st.subheader("💡 Recommendations")
            failed=[f"**{n}:** {detail}" for n,p,detail in d["checks"] if not p]
            for x in failed: st.markdown("- "+x)
            if not failed: st.success("No major issues detected by the current checks.")

            st.download_button("⬇️ Download SEO Audit CSV",df.to_csv(index=False).encode(),
                               "seo_audit_v2.csv","text/csv")
        except requests.RequestException as e:
            st.error(f"Could not access the website: {e}")
        except Exception as e:
            st.error(f"Audit error: {e}")

st.divider()
st.caption("SEO Auditor Pro v2 • Development build")
