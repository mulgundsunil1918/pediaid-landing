#!/usr/bin/env python3
"""
Generates landing/resources/<slug>/index.html for every entry in
resources_data.json, plus resources.html (category-grouped hub) and
merges resource URLs into sitemap.xml alongside the tool pages.

Run from landing/:
    python3 scripts/generate_resource_pages.py

Each resource is a file already hosted on Google Drive (public "anyone
with the link" folder) — this script does not upload or touch the
files themselves, only generates the SEO landing pages that link to them.
"""
import json
import html
import datetime
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # landing/
DATA_FILE = ROOT / "resources_data.json"
TOOLS_DATA_FILE = ROOT / "tools_data.json"
OUT_DIR = ROOT / "resources"
TODAY = datetime.date.today().isoformat()


def esc(s):
    return html.escape(str(s), quote=True)


def load_site():
    return json.loads(TOOLS_DATA_FILE.read_text(encoding="utf-8"))["site"]


def load_resources():
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["resources"]


def drive_view_url(drive_id):
    return f"https://drive.google.com/file/d/{drive_id}/view"


def related_resources(current, all_res, n=4):
    same_cat = [r for r in all_res if r["category"] == current["category"] and r["slug"] != current["slug"]]
    others = [r for r in all_res if r["category"] != current["category"] and r["slug"] != current["slug"]]
    picked = same_cat[:n]
    if len(picked) < n:
        picked += others[: n - len(picked)]
    return picked


def render_related_html(related):
    if not related:
        return ""
    cards = "\n".join(
        f'''        <a class="related-tool" href="../{r["slug"]}/">
          <h4>{esc(r["title"])}</h4>
          <p>{esc(r["category"])}</p>
        </a>'''
        for r in related
    )
    return f'''
    <div class="content-card glass">
      <h2><span class="num">2</span> Related resources</h2>
      <div class="related-grid">
{cards}
      </div>
    </div>'''


def build_jsonld(res, canonical_url, site):
    return json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "DigitalDocument",
                "@id": f"{canonical_url}#doc",
                "name": res["title"],
                "description": res["description"],
                "url": canonical_url,
                "encodingFormat": "application/pdf" if res["filename"].lower().endswith(".pdf") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "isAccessibleForFree": True,
                "publisher": {"@type": "Organization", "name": site["orgName"], "url": site["appDomain"]},
                "dateModified": TODAY,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f'{site["domain"]}/'},
                    {"@type": "ListItem", "position": 2, "name": "Resources", "item": f'{site["domain"]}/resources.html'},
                    {"@type": "ListItem", "position": 3, "name": res["title"], "item": canonical_url},
                ],
            },
        ],
    }, ensure_ascii=False, indent=2)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} | PediAid Resources</title>
<meta name="description" content="{meta_description}" />
<link rel="canonical" href="{canonical_url}" />
<meta name="theme-color" content="#1e3a5f" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{title} | PediAid Resources" />
<meta property="og:description" content="{meta_description}" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:site_name" content="PediAid" />
<meta property="og:image" content="{site_domain}/assets/pediaid-logo.png" />

<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{title} | PediAid Resources" />
<meta name="twitter:description" content="{meta_description}" />

<link rel="icon" type="image/png" href="../../assets/pediaid-logo.png"/>
<link rel="stylesheet" href="../../assets/tools.css" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>

<nav class="nav glass">
  <a class="brand" href="../../index.html">
    <span class="brand-logo" aria-hidden="true"><img src="../../assets/pediaid-logo.png" alt="PediAid" /></span>
    PediAid
  </a>
  <div class="nav-spacer"></div>
  <div class="nav-links">
    <a href="../../index.html#tools">Tools</a>
    <a href="../../resources.html">Resources</a>
    <a href="../../index.html#download">Get the app</a>
  </div>
  <a class="nav-cta" href="{app_domain}" target="_blank" rel="noopener">Open web app &rarr;</a>
</nav>

<div class="wrap">
  <div class="breadcrumb">
    <a href="../../index.html">Home</a><span class="sep">/</span>
    <a href="../../resources.html">Resources</a><span class="sep">/</span>
    <span class="current">{title}</span>
  </div>
</div>

<section class="tool-hero">
  <div class="wrap narrow">
    <span class="eyebrow"><span class="dot"></span> {category}</span>
    <h1>{title}</h1>
    <p class="lead">{description}</p>
    <div class="tool-hero-ctas">
      <a class="btn btn-primary" href="{drive_url}" target="_blank" rel="noopener">Download PDF &rarr;</a>
      <a class="btn btn-ghost" href="../../resources.html">&larr; All resources</a>
    </div>
  </div>
</section>

<section>
  <div class="wrap narrow">

    <div class="content-card glass">
      <h2><span class="num">1</span> About this file</h2>
      <p>{description}</p>
      <div class="callout">File: {filename}</div>
    </div>
{related_html}

    <div class="disclaimer">
      <strong>For qualified clinicians.</strong> This document is provided as a clinical
      reference aid only. Verify content against the current source publication and your
      local protocols before relying on it for patient care.
    </div>

  </div>
</section>

<footer>
  <div class="wrap">
    <div class="footer-row glass">
      <div>
        <strong style="color:var(--navy);">PediAid</strong> &middot; Paediatric &amp; Neonatal Clinical Reference
        <div class="muted" style="margin-top:2px;">&copy; {year} PediAid. All rights reserved.</div>
      </div>
      <div>
        <a href="{app_domain}" target="_blank" rel="noopener">Open the app</a>
        <a href="../../privacy.html">Privacy</a>
        <a href="mailto:mulgundsunil@gmail.com">Contact</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
"""


def generate_pages(site, resources):
    OUT_DIR.mkdir(exist_ok=True)
    urls = []
    for res in resources:
        canonical_url = f'{site["domain"]}/resources/{res["slug"]}/'
        meta_description = res["description"][:155].rsplit(" ", 1)[0] + "…" if len(res["description"]) > 155 else res["description"]
        related = related_resources(res, resources, n=4)
        jsonld = build_jsonld(res, canonical_url, site)

        page = PAGE_TEMPLATE.format(
            title=esc(res["title"]),
            meta_description=esc(meta_description),
            canonical_url=canonical_url,
            site_domain=site["domain"],
            app_domain=site["appDomain"],
            jsonld=jsonld,
            category=esc(res["category"]),
            description=esc(res["description"]),
            drive_url=drive_view_url(res["driveId"]),
            filename=esc(res["filename"]),
            related_html=render_related_html(related),
            year=datetime.date.today().year,
        )
        out_path = OUT_DIR / res["slug"]
        out_path.mkdir(exist_ok=True)
        (out_path / "index.html").write_text(page, encoding="utf-8")
        urls.append(canonical_url)
    return urls


def generate_hub(site, resources):
    by_category = {}
    for r in resources:
        by_category.setdefault(r["category"], []).append(r)
    sections = []
    for cat in sorted(by_category):
        cards = "\n".join(
            f'''        <a class="related-tool" href="resources/{r["slug"]}/">
          <h4>{esc(r["title"])}</h4>
          <p>{esc(r["filename"])}</p>
        </a>'''
            for r in by_category[cat]
        )
        sections.append(f'''    <div class="content-card glass">
      <h2>{esc(cat)}</h2>
      <div class="related-grid">
{cards}
      </div>
    </div>''')
    body = "\n\n".join(sections)
    canonical = f'{site["domain"]}/resources.html'
    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Downloadable Resources — PediAid</title>
<meta name="description" content="Free downloadable PDFs for paediatric and neonatal practice — growth charts, BP charts, scoring systems, guidelines and teaching templates, organised by category." />
<link rel="canonical" href="{canonical}" />
<meta name="theme-color" content="#1e3a5f" />
<link rel="icon" type="image/png" href="assets/pediaid-logo.png"/>
<link rel="stylesheet" href="assets/tools.css" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
</head>
<body>

<nav class="nav glass">
  <a class="brand" href="index.html">
    <span class="brand-logo" aria-hidden="true"><img src="assets/pediaid-logo.png" alt="PediAid" /></span>
    PediAid
  </a>
  <div class="nav-spacer"></div>
  <div class="nav-links">
    <a href="index.html#tools">Tools</a>
    <a href="all-tools.html">All Tools</a>
    <a href="index.html#download">Get the app</a>
  </div>
  <a class="nav-cta" href="{site["appDomain"]}" target="_blank" rel="noopener">Open web app &rarr;</a>
</nav>

<div class="wrap">
  <div class="breadcrumb">
    <a href="index.html">Home</a><span class="sep">/</span>
    <span class="current">Resources</span>
  </div>
</div>

<section class="tool-hero">
  <div class="wrap narrow">
    <span class="eyebrow"><span class="dot"></span> {len(resources)} Downloads</span>
    <h1>Downloadable clinical resources</h1>
    <p class="lead">Free PDFs for paediatric and neonatal practice — growth charts, BP charts, scoring systems, official guidelines and teaching templates.</p>
  </div>
</section>

<section>
  <div class="wrap narrow">
{body}
  </div>
</section>

<footer>
  <div class="wrap">
    <div class="footer-row glass">
      <div>
        <strong style="color:var(--navy);">PediAid</strong> &middot; Paediatric &amp; Neonatal Clinical Reference
        <div class="muted" style="margin-top:2px;">&copy; {datetime.date.today().year} PediAid. All rights reserved.</div>
      </div>
      <div>
        <a href="{site["appDomain"]}" target="_blank" rel="noopener">Open the app</a>
        <a href="privacy.html">Privacy</a>
        <a href="mailto:mulgundsunil@gmail.com">Contact</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''
    (ROOT / "resources.html").write_text(page, encoding="utf-8")
    return canonical


def merge_sitemap(new_urls):
    sitemap_path = ROOT / "sitemap.xml"
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    existing = {loc.text for loc in root.findall(f"{ns}url/{ns}loc")}
    added = 0
    for u in new_urls:
        if u in existing:
            continue
        url_el = ET.SubElement(root, f"{ns}url")
        loc_el = ET.SubElement(url_el, f"{ns}loc")
        loc_el.text = u
        lastmod_el = ET.SubElement(url_el, f"{ns}lastmod")
        lastmod_el.text = TODAY
        added += 1
    ET.register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
    tree.write(sitemap_path, encoding="UTF-8", xml_declaration=True)
    return added, len(existing) + added


def main():
    site = load_site()
    resources = load_resources()
    urls = generate_pages(site, resources)
    hub_url = generate_hub(site, resources)
    added, total = merge_sitemap(urls + [hub_url])
    print(f"Generated {len(urls)} resource pages + resources.html hub.")
    print(f"sitemap.xml: +{added} new URLs ({total} total)")


if __name__ == "__main__":
    main()
