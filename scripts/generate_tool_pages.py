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
import re
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


# Category-aware <title>. The old template was "{title} | PediAid", which
# repeated the H1 and targeted nobody's search phrasing. A tool may override it
# with an explicit "seoTitle" in tools_data.json; otherwise the category picks a
# qualifier that matches how clinicians actually search.
_TITLE_QUALIFIER = {
    "Calculators & Tools": "Calculator",
    "Charts": "Chart — Percentiles & Z-Scores",
    "Drug Formulary": "Dosing Reference",
    "Emergency": "Protocol",
    "Guides": "Guide",
    "Lab Reference": "Normal Values",
    "Academics": "",
}


def seo_title_for(tool):
    """Build the <title>. The " | PediAid" suffix is dropped when a clinical
    name is already long — Google truncates around 65 characters, and losing
    the end of "Eosinophilic Granulomatosis with Polyangiitis" to keep a brand
    tag is the wrong trade."""
    explicit = tool.get("seoTitle")
    if explicit:
        return explicit if len(explicit) > 58 else f"{explicit} | PediAid"
    base = tool.get("primaryKeyword") or tool["title"]
    qual = _TITLE_QUALIFIER.get(tool.get("category", ""), "")
    # Don't produce "... Calculator Calculator".
    if qual and qual.split()[0].lower() in base.lower():
        qual = ""
    head = f"{base} {qual}".strip() if qual else base
    return f"{head} | PediAid"


# Words a description must never end on — cutting after them leaves the reader
# hanging even though the string technically stops at a boundary.
_DANGLING = {
    "and", "or", "but", "with", "for", "from", "that", "which", "who", "the",
    "a", "an", "to", "in", "of", "on", "at", "by", "as", "into", "than",
    "when", "while", "where", "its", "their", "this", "these", "each", "per",
}


def meta_description_for(tool, content, limit=158):
    """A description that ends as a finished thought, never mid-clause.

    The previous version sliced ``intro[:155]`` and appended an ellipsis, so
    all 227 pages shipped a snippet that stopped dead ("...for..."). Google
    rewrites a bad description often enough, but never into something better
    than one written to fit, and the ellipsis reads as broken in the SERP.

    Order of preference: whole sentences, then whole clauses of the first
    sentence, then whole words -- and a full stop in every case.
    """
    intro = re.sub(r"\s+", " ", content.get("intro", "")).strip()
    if not intro:
        sub = re.sub(r"\s+", " ", tool.get("subtitle") or "").strip()
        base = f'{tool["title"]} - {sub}' if sub else tool["title"]
        return (base.rstrip(" .") + ".")[:limit]

    # 1. As many complete sentences as fit. The lookahead keeps "et al." and
    #    "P50." from being read as sentence ends.
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", intro)
    out = ""
    for s in sentences:
        cand = f"{out} {s}".strip() if out else s
        if len(cand) > limit:
            break
        out = cand
    if out:
        return out

    # 2. The first sentence alone overshoots: keep whole clauses of it.
    #    Strong breaks (dash, colon, semicolon) are tried before commas --
    #    cutting at a comma inside a list leaves "...four levels: Alert, Voice,
    #    Pain.", which reads worse than stopping at the colon.
    first = sentences[0]
    best = ""
    for pattern in (r";|:| - |\u2014|\u2013", r","):
        for m in re.finditer(pattern, first):
            head = first[: m.start()].rstrip()
            if len(head) + 1 > limit:
                break
            best = head
        if best:
            break
    if not best:
        # 3. No clause boundary in range -- fall back to whole words.
        words = first.split()
        acc = []
        for w in words:
            if len(" ".join(acc + [w])) + 1 > limit:
                break
            acc.append(w)
        best = " ".join(acc)

    while best and best.split()[-1].strip(",;:-").lower() in _DANGLING:
        best = " ".join(best.split()[:-1])
    best = best.rstrip(" ,;:-\u2014\u2013.")
    return (best + ".") if best else tool["title"] + "."


# ── Topic hubs ──────────────────────────────────────────────────────────────
#
# Every tool page used to hang directly off all-tools.html, so 227 pages sat in
# one flat layer with a single parent. That gives Google nothing to read as
# topical structure and spreads internal links thinly across the whole set.
# These hubs are the intermediate layer: each is a real page that can rank for
# the category query in its own right ("paediatric calculators", "paediatric
# clinical scores"), and each concentrates links onto the tools beneath it.
#
# Keys must stay stable -- they are URL segments.
HUBS = {
    "calculators": {
        "name": "Calculators",
        "title": "Paediatric &amp; Neonatal Calculators — Free Bedside Tools",
        "description": "Free paediatric and neonatal calculators: fluids, TPN, GIR, "
                       "bilirubin, blood pressure percentiles, ETT size, corrected "
                       "sodium, eGFR and more. Each shows its formula and source.",
        "heading": "Paediatric and neonatal calculators",
        "lead": "Bedside calculators for paediatric and neonatal practice — fluids and "
                "electrolytes, nutrition, respiratory support, jaundice, cardiology and "
                "emergency dosing. Every calculator shows the formula it used and the "
                "reference it came from, so the number can be checked rather than "
                "trusted blindly, and all of them work offline in the app.",
    },
    "scores": {
        "name": "Clinical Scores",
        "title": "Paediatric Clinical Scores &amp; Diagnostic Criteria",
        "description": "Paediatric clinical scores and diagnostic criteria across 15 "
                       "specialties — with the exact criteria, weights, severity bands "
                       "and source publication for each.",
        "heading": "Paediatric clinical scores and criteria",
        "lead": "Severity scores and diagnostic criteria used across paediatrics, grouped "
                "by system. Each page lists the exact criteria and the weight each "
                "carries, the severity bands the total falls into, and the publication "
                "the score comes from — so an infrequently-used score can be checked "
                "before it is relied on.",
    },
    "charts": {
        "name": "Growth Charts",
        "title": "Growth Charts — WHO, IAP, Fenton &amp; INTERGROWTH-21st",
        "description": "Plot weight, length and head circumference on WHO, IAP 2015, "
                       "Fenton preterm and INTERGROWTH-21st references, with percentiles, "
                       "Z-scores and PDF export.",
        "heading": "Growth charts",
        "lead": "Plot a child's measurements against the four growth references paediatric "
                "practice actually uses — WHO, IAP 2015, Fenton for preterm infants and "
                "INTERGROWTH-21st. Each returns the percentile and Z-score for weight, "
                "length and head circumference, and exports the plotted chart as a PDF "
                "for the record.",
    },
    "guides": {
        "name": "Guides &amp; Protocols",
        "title": "Paediatric Clinical Guides &amp; Protocols",
        "description": "Paediatric and neonatal clinical guides: NRP, PALS, DKA, "
                       "immunisation schedules, developmental milestones, gestational-age "
                       "classification and neonatal echocardiography.",
        "heading": "Clinical guides and protocols",
        "lead": "Reference guides for the protocols that have to be right first time — "
                "resuscitation algorithms, DKA management, immunisation schedules with "
                "catch-up, developmental milestones and gestational-age classification. "
                "Written to be read at the bedside rather than skimmed in advance.",
    },
    "emergency": {
        "name": "Emergency",
        "title": "Paediatric Emergency &amp; Toxicology Protocols",
        "description": "Paediatric emergency references — envenomation, poisoning and "
                       "antidotes, status asthmaticus, shock and resuscitation dosing, "
                       "with the doses and thresholds in one place.",
        "heading": "Emergency and toxicology",
        "lead": "The references that get opened under time pressure: snake and scorpion "
                "envenomation, poisoning and antidotes, status asthmaticus, shock and "
                "resuscitation dosing. Doses, thresholds and escalation points are stated "
                "directly rather than buried in prose.",
    },
    "reference": {
        "name": "Reference",
        "title": "Paediatric Drug Formulary &amp; Lab Reference Values",
        "description": "Paediatric drug dosing, normal laboratory reference values by age, "
                       "and the PediAid Academics library of trials, guidelines and CME.",
        "heading": "Drug formulary, lab values and academics",
        "lead": "Dosing and reference data, plus the reading that sits behind it — a "
                "paediatric drug formulary, age-banded normal laboratory values, and the "
                "Academics library of landmark trial reviews, guideline notes and CME "
                "listings.",
    },
}

# Score-hub sub-grouping. Sorted by how many scores each carries, so the
# densest specialties lead the page rather than alphabetical accident.
_SYSTEM_ORDER = [
    "GI & Liver", "Psychosocial", "Oncology", "Infectious", "Rheumatology",
    "Respiratory", "Neurology & trauma", "Cardiac", "Critical care", "Pain",
    "Haematology", "Endocrine", "Renal", "Radiology", "Sleep",
]


def hub_for(tool):
    """Hub slug for a tool. Falls back to calculators so a tool added to the
    catalogue without a hub still gets a parent rather than being orphaned."""
    h = tool.get("hub")
    return h if h in HUBS else "calculators"


def load_content(slug):
    f = CONTENT_DIR / f"{slug}.json"
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def related_tools(current, all_tools, n=4):
    """Nearest neighbours first: same system, then same hub, then anything.

    Grouping by the old flat `category` meant a psychosocial score linked to
    four unrelated GI scores purely because both sat in "Calculators & Tools".
    Related links are the main way link equity moves between leaf pages, so
    they are worth pointing at genuinely adjacent tools."""
    rest = [t for t in all_tools if t["slug"] != current["slug"]]
    hub = hub_for(current)
    sys_ = current.get("system")

    same_system = [t for t in rest if sys_ and t.get("system") == sys_ and hub_for(t) == hub]
    same_hub = [t for t in rest if hub_for(t) == hub and t not in same_system]
    others = [t for t in rest if hub_for(t) != hub]

    picked = []
    for pool in (same_system, same_hub, others):
        for t in pool:
            if len(picked) >= n:
                return picked
            picked.append(t)
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
    hub = hub_for(tool)
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
            "publisher": {"@id": f'{site["domain"]}/#organization'},
            "isPartOf": {"@id": f'{site["domain"]}/#website'},
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
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": html.unescape(HUBS[hub]["name"]),
                    "item": f'{site["domain"]}/{hub}/',
                },
                {"@type": "ListItem", "position": 3, "name": tool["title"], "item": canonical_url},
            ],
        }
    )
    if faq_entities:
        graph.append({"@type": "FAQPage", "mainEntity": faq_entities})
    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, indent=2)


HUB_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{seo_title}</title>
<meta name="description" content="{meta_description}" />
<link rel="canonical" href="{canonical_url}" />
<meta name="theme-color" content="#1e3a5f" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{og_title}" />
<meta property="og:description" content="{meta_description}" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:site_name" content="PediAid" />
<meta property="og:image" content="{site_domain}/assets/og-image.jpg" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{og_title}" />
<meta name="twitter:description" content="{meta_description}" />
<meta name="twitter:image" content="{site_domain}/assets/og-image.jpg" />

<link rel="icon" type="image/png" href="../assets/pediaid-logo.png"/>
<link rel="apple-touch-icon" href="../assets/pediaid-logo.png" />
<link rel="stylesheet" href="../assets/tools.css" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">

<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>

<nav class="nav glass">
  <a class="brand" href="../index.html">
    <span class="brand-logo" aria-hidden="true"><img src="../assets/pediaid-logo.png" alt="PediAid" /></span>
    PediAid
  </a>
  <div class="nav-spacer"></div>
  <div class="nav-links">
    <a href="../index.html#features">Features</a>
    <a href="../all-tools.html">All tools</a>
    <a href="../index.html#download">Get the app</a>
  </div>
  <a class="nav-cta" href="{app_domain}" target="_blank" rel="noopener">Open web app &rarr;</a>
</nav>

<div class="wrap">
  <div class="breadcrumb">
    <a href="../index.html">Home</a><span class="sep">/</span>
    <span class="current">{hub_name}</span>
  </div>
</div>

<section class="tool-hero">
  <div class="wrap narrow">
    <span class="eyebrow"><span class="dot"></span> {count} in this section</span>
    <h1>{heading}</h1>
    <p class="lead">{lead}</p>
    <div class="tool-hero-ctas">
      <a class="btn btn-primary" href="{app_domain}" target="_blank" rel="noopener">Open in PediAid &rarr;</a>
      <a class="btn btn-ghost" href="../all-tools.html">&larr; All tools</a>
    </div>
  </div>
</section>

<section>
  <div class="wrap narrow">
{body}

    <div class="content-card glass">
      <h2>Elsewhere in PediAid</h2>
      <div class="related-grid">
{siblings}
      </div>
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
        <a href="../privacy.html">Privacy</a>
        <a href="mailto:help@bridgr.co.in">Contact</a>
      </div>
    </div>
  </div>
</footer>

</body>
</html>
"""


def _tool_cards(items, prefix="../tools/"):
    return "\n".join(
        '        <a class="related-tool" href="%s%s/">\n'
        '          <h4>%s</h4>\n'
        '          <p>%s</p>\n'
        '        </a>' % (prefix, t["slug"], esc(t["title"]), esc(t["subtitle"]))
        for t in items
    )


def build_hub_pages(site, tools, generated):
    """One page per hub, plus the sibling cross-links between them.

    The scores hub is sub-grouped by clinical system: 95 cards in one
    undifferentiated grid is not a page anyone reads, and the system headings
    are themselves the phrasing people search ("paediatric respiratory
    scores").
    """
    live = [t for t in tools if t["slug"] in generated]
    by_hub = {}
    for t in live:
        by_hub.setdefault(hub_for(t), []).append(t)

    written = []
    for hub, cfg in HUBS.items():
        items = sorted(by_hub.get(hub, []), key=lambda t: t["title"])
        if not items:
            continue
        canonical_url = "%s/%s/" % (site["domain"], hub)

        # Body: systems as sections for scores, one grid for everything else.
        if hub == "scores":
            groups = {}
            for t in items:
                groups.setdefault(t.get("system") or "General", []).append(t)
            ordered = [x for x in _SYSTEM_ORDER if x in groups]
            ordered += sorted(k for k in groups if k not in ordered)
            body = "\n\n".join(
                '    <div class="content-card glass">\n'
                '      <h2>%s <span class="muted" style="font-weight:500;">&middot; %d</span></h2>\n'
                '      <div class="related-grid">\n%s\n      </div>\n'
                '    </div>' % (esc(sys_), len(groups[sys_]), _tool_cards(groups[sys_]))
                for sys_ in ordered
            )
        else:
            body = (
                '    <div class="content-card glass">\n'
                '      <h2>%s</h2>\n'
                '      <div class="related-grid">\n%s\n      </div>\n'
                '    </div>' % (html.unescape(cfg["name"]), _tool_cards(items))
            )

        siblings = "\n".join(
            '        <a class="related-tool" href="../%s/">\n'
            '          <h4>%s</h4>\n'
            '          <p>%d pages</p>\n'
            '        </a>' % (h, other["name"], len(by_hub.get(h, [])))
            for h, other in HUBS.items()
            if h != hub and by_hub.get(h)
        )

        jsonld = json.dumps(
            {
                "@context": "https://schema.org",
                "@graph": [
                    {
                        "@type": "CollectionPage",
                        "@id": canonical_url + "#webpage",
                        "url": canonical_url,
                        "name": html.unescape(cfg["title"]),
                        "description": html.unescape(cfg["description"]),
                        "inLanguage": "en",
                        "isPartOf": {"@id": site["domain"] + "/#website"},
                        "publisher": {"@id": site["domain"] + "/#organization"},
                    },
                    {
                        "@type": "ItemList",
                        "name": html.unescape(cfg["heading"]),
                        "numberOfItems": len(items),
                        "itemListElement": [
                            {
                                "@type": "ListItem",
                                "position": i,
                                "name": t["title"],
                                "url": "%s/tools/%s/" % (site["domain"], t["slug"]),
                            }
                            for i, t in enumerate(items, 1)
                        ],
                    },
                    {
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {"@type": "ListItem", "position": 1, "name": "Home",
                             "item": site["domain"] + "/"},
                            {"@type": "ListItem", "position": 2,
                             "name": html.unescape(cfg["name"]), "item": canonical_url},
                        ],
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

        page = HUB_TEMPLATE.format(
            seo_title="%s | PediAid" % cfg["title"],
            og_title=cfg["title"],
            meta_description=cfg["description"],
            canonical_url=canonical_url,
            site_domain=site["domain"],
            app_domain=site["appDomain"],
            hub_name=cfg["name"],
            heading=cfg["heading"],
            lead=cfg["lead"],
            count=len(items),
            body=body,
            siblings=siblings,
            jsonld=jsonld,
            year=datetime.date.today().year,
        )
        out = ROOT / hub
        out.mkdir(exist_ok=True)
        (out / "index.html").write_text(page, encoding="utf-8")
        written.append(hub)

    return written


PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{seo_title}</title>
<meta name="description" content="{meta_description}" />
<link rel="canonical" href="{canonical_url}" />
<meta name="theme-color" content="#1e3a5f" />

<meta property="og:type" content="website" />
<meta property="og:title" content="{title} | PediAid" />
<meta property="og:description" content="{meta_description}" />
<meta property="og:url" content="{canonical_url}" />
<meta property="og:site_name" content="PediAid" />
<meta property="og:image" content="{site_domain}/assets/og-image.jpg" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{title} | PediAid" />
<meta name="twitter:description" content="{meta_description}" />
<meta name="twitter:image" content="{site_domain}/assets/og-image.jpg" />

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
    <a href="../../{hub_slug}/">{hub_name}</a><span class="sep">/</span>
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
      <a class="btn btn-ghost" href="../../{hub_slug}/">&larr; All {hub_name_lower}</a>
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
        seo_title = seo_title_for(tool)
        if content is None:
            skipped.append(tool["slug"])
            continue

        canonical_url = f'{site["domain"]}/tools/{tool["slug"]}/'
        meta_description = meta_description_for(tool, content)
        related = related_tools(tool, tools, n=4)
        jsonld = build_jsonld(tool, content, canonical_url, site)

        external_url = tool.get("externalUrl")
        cta_href = external_url if external_url else f'{site["appDomain"]}/#{tool["slug"]}'
        cta_label = "Open Official Calculator" if external_url else "Open in PediAid"

        hub = hub_for(tool)
        page = PAGE_TEMPLATE.format(
            hub_slug=hub,
            hub_name=HUBS[hub]["name"],
            hub_name_lower=HUBS[hub]["name"].lower(),
            title=esc(tool["title"]),
            seo_title=esc(seo_title),
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
    by_hub = {}
    for tool in tools:
        if tool["slug"] in generated:
            by_hub.setdefault(hub_for(tool), []).append(tool)
    sections = []
    for hub, cfg in HUBS.items():
        items = sorted(by_hub.get(hub, []), key=lambda t: t["title"])
        if not items:
            continue
        cards = _tool_cards(items, prefix="tools/")
        # Each section header links to its hub, so the hub pages are reachable
        # from here as well as from the homepage nav.
        sections.append(f'''    <div class="content-card glass">
      <h2><a href="{hub}/" style="color:inherit;">{cfg["name"]}</a> <span class="muted" style="font-weight:500;">&middot; {len(items)}</span></h2>
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

<meta property="og:type" content="website" />
<meta property="og:title" content="All Tools &mdash; PediAid Calculators, Charts &amp; Guides" />
<meta property="og:description" content="Every calculator, growth chart and clinical guide in PediAid &mdash; {len(generated)} free paediatric and neonatal tools, organised by category." />
<meta property="og:url" content="{all_tools_canonical}" />
<meta property="og:site_name" content="PediAid" />
<meta property="og:image" content="{site["domain"]}/assets/og-image.jpg" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />

<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="All Tools &mdash; PediAid Calculators, Charts &amp; Guides" />
<meta name="twitter:image" content="{site["domain"]}/assets/og-image.jpg" />

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
    #
    # This generator owns the core pages and everything under /tools/. It used
    # to rewrite the whole file, which silently deleted the 28 resource URLs
    # that generate_resource_pages.py merges in -- the live sitemap carried
    # 230 tool URLs and not one resource page. Anything outside this
    # generator's own namespace is now carried through untouched.
    hubs_written = build_hub_pages(site, tools, generated)
    print(f"Generated {len(hubs_written)} hub pages: {', '.join(hubs_written)}")

    owned = [f'{site["domain"]}/', f'{site["domain"]}/privacy.html', all_tools_canonical] + [
        f'{site["domain"]}/{h}/' for h in hubs_written
    ] + [
        f'{site["domain"]}/tools/{slug}/' for slug in generated
    ]
    owned_set = set(owned)
    tools_prefix = f'{site["domain"]}/tools/'

    carried = []
    sitemap_path = ROOT / "sitemap.xml"
    if sitemap_path.exists():
        existing = sitemap_path.read_text(encoding="utf-8")
        for m in re.finditer(r"<url>\s*<loc>(.*?)</loc>(.*?)</url>", existing, re.S):
            loc = html.unescape(m.group(1).strip())
            if loc in owned_set or loc.startswith(tools_prefix):
                continue  # this generator re-emits it below
            if any(loc == f'{site["domain"]}/{h}/' for h in HUBS):
                continue  # this generator re-emits it below
            lastmod = re.search(r"<lastmod>(.*?)</lastmod>", m.group(2))
            carried.append((loc, lastmod.group(1) if lastmod else TODAY))

    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in owned:
        sitemap.append(f"  <url><loc>{esc(u)}</loc><lastmod>{TODAY}</lastmod></url>")
    for loc, lastmod in carried:
        sitemap.append(f"  <url><loc>{esc(loc)}</loc><lastmod>{esc(lastmod)}</lastmod></url>")
    sitemap.append("</urlset>")
    sitemap_path.write_text("\n".join(sitemap) + "\n", encoding="utf-8")
    urls = owned + [c[0] for c in carried]
    if carried:
        print(f"  carried through {len(carried)} non-tool URLs (resources etc.)")

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
