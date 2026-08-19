#!/usr/bin/env python3
"""
Generates landing/tools/<slug>/index.html for every tool in tools_data.json,
plus sitemap.xml and robots.txt. Pure stdlib — no dependencies to install,
matching the rest of this static-HTML repo.

Run from anywhere; paths are resolved relative to this script's location:
    python3 landing/scripts/generate_tool_pages.py

Content comes from two places, kept deliberately separate:
  tools_data.json          - structural catalog (slug, title, keywords, category)
  tools_content/<slug>.json - grounded clinical content (intro/indications/faqs/etc)

A tool with no content file is skipped with a warning rather than generating
a thin/empty page.
"""
import json
import html
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # landing/
DATA_FILE = ROOT / "tools_data.json"
CONTENT_DIR = ROOT / "tools_content"
OUT_DIR = ROOT / "tools"
TODAY = datetime.date.today().isoformat()


def esc(s):
    return html.escape(str(s), quote=True)


def load_catalog():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return data["site"], data["tools"]


def load_content(slug):
    f = CONTENT_DIR / f"{slug}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def related_tools(current, all_tools, n=4):
    same_cat = [t for t in all_tools if t["category"] == current["category"] and t["slug"] != current["slug"]]
    others = [t for t in all_tools if t["category"] != current["category"] and t["slug"] != current["slug"]]
    picked = same_cat[:n]
    if len(picked) < n:
        picked += others[: n - len(picked)]
    return picked


def render_faq_html(faqs):
    if not faqs:
        return ""
    items = "\n".join(
        f'''      <div class="faq-item">
        <h3>{esc(f["q"])}</h3>
        <p>{esc(f["a"])}</p>
      </div>'''
        for f in faqs
    )
    return f'''
    <div class="content-card glass">
      <h2><span class="num">4</span> Frequently asked questions</h2>
{items}
    </div>'''


def render_related_html(related, site_domain):
    if not related:
        return ""
    cards = "\n".join(
        f'''        <a class="related-tool" href="../{r["slug"]}/">
          <h4>{esc(r["title"])}</h4>
          <p>{esc(r["subtitle"])}</p>
        </a>'''
        for r in related
    )
    return f'''
    <div class="content-card glass">
      <h2><span class="num">5</span> Related tools</h2>
      <div class="related-grid">
{cards}
      </div>
    </div>'''


def render_indications_html(indications):
    if not indications:
        return "<p>See the in-app tool for full usage guidance.</p>"
    items = "\n".join(f"        <li>{esc(i)}</li>" for i in indications)
    return f"<ul class=\"plain\">\n{items}\n      </ul>"


def render_refs_html(refs):
    if not refs:
        return ""
    items = "\n".join(f"        <li>{esc(r)}</li>" for r in refs)
    return f'\n      <ul class="callout-refs">\n{items}\n      </ul>'


def build_jsonld(tool, content, canonical_url, site):
    faq_entities = [
        {
            "@type": "Question",
            "name": f["q"],
            "acceptedAnswer": {"@type": "Answer", "text": f["a"]},
        }
        for f in content.get("faqs", [])
    ]
    graph = [
        {
            "@type": "MedicalWebPage",
            "@id": f"{canonical_url}#webpage",
            "url": canonical_url,
            "name": f'{tool["title"]} | PediAid',
            "description": content["intro"][:300],
            "inLanguage": "en",
            "about": {"@type": "MedicalEntity", "name": tool["title"]},
            "publisher": {"@type": "Organization", "name": site["orgName"], "url": site["appDomain"]},
            "lastReviewed": TODAY,
        },
    ]
    # External-link tools (BPD, INTERGROWTH, TnECHO) aren't PediAid's own
    # software — don't claim a SoftwareApplication for someone else's tool.
    if not tool.get("externalUrl"):
        graph.append({
            "@type": "SoftwareApplication",
            "name": f'PediAid — {tool["title"]}',
            "applicationCategory": "HealthApplication",
            "operatingSystem": "Web, Android, iOS",
            "url": f'{site["appDomain"]}/#{tool["slug"]}',
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        })
    graph.append(
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": f'{site["domain"]}/'},
                {"@type": "ListItem", "position": 2, "name": "Tools", "item": f'{site["domain"]}/#tools'},
                {"@type": "ListItem", "position": 3, "name": tool["title"], "item": canonical_url},
            ],
        }
    )
    if faq_entities:
        graph.append({"@type": "FAQPage", "mainEntity": faq_entities})
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title} | PediAid</title>
<meta name="description" content="{meta_description}" />
<link rel="canonical" href="{canonical_url}" />
<meta name="theme-color" content="#1e3a5f" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{title} | PediAid" />
<meta property="og:description" content="{meta_description}" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:site_name" content="PediAid" />
<meta property="og:image" content="{site_domain}/assets/pediaid-logo.png" />

<meta name="twitter:card" content="summary" />
<meta name="twitter:title" content="{title} | PediAid" />
<meta name="twitter:description" content="{meta_description}" />
<meta name="twitter:image" content="{site_domain}/assets/pediaid-logo.png" />

<link rel="icon" type="image/png" href="../../assets/pediaid-logo.png"/>
<link rel="apple-touch-icon" href="../../assets/pediaid-logo.png" />
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
    <a href="../../index.html#features">Features</a>
    <a href="../../index.html#tools">Tools</a>
    <a href="../../index.html#download">Get the app</a>
  </div>
  <a class="nav-cta" href="{app_domain}" target="_blank" rel="noopener">Open web app &rarr;</a>
</nav>

<div class="wrap">
  <div class="breadcrumb">
    <a href="../../index.html">Home</a><span class="sep">/</span>
    <a href="../../index.html#tools">Tools</a><span class="sep">/</span>
    <span class="current">{title}</span>
  </div>
</div>

<section class="tool-hero">
  <div class="wrap narrow">
    <span class="eyebrow"><span class="dot"></span> {category}</span>
    <h1>{title}</h1>
    <p class="lead">{subtitle}</p>
    <div class="tool-hero-ctas">
      <a class="btn btn-primary" href="{deep_link}" target="_blank" rel="noopener">{cta_label} &rarr;</a>
      <a class="btn btn-ghost" href="../../index.html#tools">&larr; All tools</a>
    </div>
  </div>
</section>

<section>
  <div class="wrap narrow">

    <div class="content-card glass">
      <h2><span class="num">1</span> What is the {title}?</h2>
      <p>{intro}</p>
    </div>

    <div class="content-card glass">
      <h2><span class="num">2</span> When to use it</h2>
      {indications_html}
    </div>

    <div class="content-card glass">
      <h2><span class="num">3</span> Formula &amp; method</h2>
      <div class="callout formula">{method}</div>{refs_html}
    </div>
{faq_html}
{related_html}

    <div class="disclaimer">
      <strong>For qualified clinicians.</strong> This page and the PediAid app are a clinical
      aid only. Calculations and reference data must be verified against the patient's
      clinical context, the source guideline and your local protocols before any
      treatment decision is made.
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
        <a href="mailto:help@bridgr.co.in">Contact</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
"""


def main():
    site, tools = load_catalog()
    OUT_DIR.mkdir(exist_ok=True)
    generated = []
    skipped = []

    for tool in tools:
        content = load_content(tool["slug"])
        if content is None:
            skipped.append(tool["slug"])
            continue

        canonical_url = f'{site["domain"]}/tools/{tool["slug"]}/'
        meta_description = content["intro"][:155].rsplit(" ", 1)[0] + "…" if len(content["intro"]) > 155 else content["intro"]
        related = related_tools(tool, tools, n=4)
        jsonld = build_jsonld(tool, content, canonical_url, site)

        external_url = tool.get("externalUrl")
        cta_href = external_url if external_url else f'{site["appDomain"]}/#{tool["slug"]}'
        cta_label = "Open Official Calculator" if external_url else "Open in PediAid"

        page = PAGE_TEMPLATE.format(
            title=esc(tool["title"]),
            meta_description=esc(meta_description),
            canonical_url=canonical_url,
            site_domain=site["domain"],
            app_domain=site["appDomain"],
            deep_link=cta_href,
            cta_label=cta_label,
            jsonld=jsonld,
            category=esc(tool["category"]),
            subtitle=esc(tool["subtitle"]),
            intro=esc(content["intro"]),
            indications_html=render_indications_html(content.get("indications", [])),
            method=esc(content.get("method", "")),
            refs_html=render_refs_html(content.get("guidelineRefs", [])),
            faq_html=render_faq_html(content.get("faqs", [])),
            related_html=render_related_html(related, site["domain"]),
            year=datetime.date.today().year,
        )

        out_path = OUT_DIR / tool["slug"]
        out_path.mkdir(exist_ok=True)
        (out_path / "index.html").write_text(page, encoding="utf-8")
        generated.append(tool["slug"])

    # all-tools.html — the internal-linking hub. Sitemap.xml gets Google
    # there directly, but a real on-site page linking to all 80 tool pages
    # (not just the 16-card homepage sample) is what makes them mutually
    # discoverable through normal crawling/PageRank flow too.
    by_category = {}
    for tool in tools:
        if tool["slug"] in generated:
            by_category.setdefault(tool["category"], []).append(tool)
    sections = []
    for cat in sorted(by_category):
        cards = "\n".join(
            f'''        <a class="related-tool" href="tools/{t["slug"]}/">
          <h4>{esc(t["title"])}</h4>
          <p>{esc(t["subtitle"])}</p>
        </a>'''
            for t in by_category[cat]
        )
        sections.append(f'''    <div class="content-card glass">
      <h2>{esc(cat)}</h2>
      <div class="related-grid">
{cards}
      </div>
    </div>''')
    all_tools_body = "\n\n".join(sections)
    all_tools_canonical = f'{site["domain"]}/all-tools.html'
    all_tools_page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>All Tools — PediAid Calculators, Charts &amp; Guides</title>
<meta name="description" content="Every calculator, growth chart and clinical guide in PediAid — {len(generated)} free paediatric and neonatal tools, organised by category." />
<link rel="canonical" href="{all_tools_canonical}" />
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
    <a href="index.html#features">Features</a>
    <a href="index.html#tools">Tools</a>
    <a href="index.html#download">Get the app</a>
  </div>
  <a class="nav-cta" href="{site["appDomain"]}" target="_blank" rel="noopener">Open web app &rarr;</a>
</nav>

<div class="wrap">
  <div class="breadcrumb">
    <a href="index.html">Home</a><span class="sep">/</span>
    <span class="current">All Tools</span>
  </div>
</div>

<section class="tool-hero">
  <div class="wrap narrow">
    <span class="eyebrow"><span class="dot"></span> {len(generated)} tool guides</span>
    <h1>PediAid calculators, charts and guides</h1>
    <p class="lead">Free, offline-friendly clinical tools for paediatric and neonatal practice — organised by category. These pages cover the most-used tools; the app itself carries the full set, including the paediatric score library and immunisation catch-up planner.</p>
  </div>
</section>

<section>
  <div class="wrap narrow">
{all_tools_body}
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
        <a href="mailto:help@bridgr.co.in">Contact</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
'''
    (ROOT / "all-tools.html").write_text(all_tools_page, encoding="utf-8")

    # sitemap.xml
    urls = [f'{site["domain"]}/', f'{site["domain"]}/privacy.html', all_tools_canonical] + [
        f'{site["domain"]}/tools/{slug}/' for slug in generated
    ]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        sitemap.append(f"  <url><loc>{esc(u)}</loc><lastmod>{TODAY}</lastmod></url>")
    sitemap.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8")

    # robots.txt
    robots = f"""User-agent: *
Allow: /

Sitemap: {site["domain"]}/sitemap.xml
"""
    (ROOT / "robots.txt").write_text(robots, encoding="utf-8")

    print(f"Generated {len(generated)} tool pages.")
    if skipped:
        print(f"Skipped {len(skipped)} tools with no content file yet:")
        for s in skipped:
            print(f"  - {s}")
    print(f"sitemap.xml: {len(urls)} URLs")


if __name__ == "__main__":
    main()
