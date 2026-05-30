"""
SerDes Daily Paper Digest
Fetches from arXiv + IEEE Xplore + Google Scholar, sends a rich HTML email via Resend.com.
No SMTP. No passwords. Just API keys stored in GitHub Secrets.
"""

import os
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

# ─── CONFIG (set via GitHub Secrets / Variables) ───────────────────────────────
DIGEST_EMAIL = os.getenv("DIGEST_EMAIL", "")          # your email address
RESEND_KEY   = os.getenv("RESEND_API_KEY", "")        # from resend.com (free)
IEEE_KEY     = os.getenv("IEEE_API_KEY", "")          # from developer.ieee.org (free, optional)
SERPAPI_KEY  = os.getenv("SERPAPI_KEY", "")           # from serpapi.com (free tier, optional)
FROM_EMAIL   = os.getenv("FROM_EMAIL", "digest@resend.dev")

MAX_RESULTS = 12
START_YEAR  = (datetime.now() - timedelta(days=180)).year

# ─── SOURCE-SPECIFIC OPTIMIZED QUERIES ────────────────────────────────────────
# arXiv: field-targeted — ti: = title, abs: = abstract
# Covers CDR, equalization (DFE/FFE/CTLE), high-speed links, ADC-based receivers
ARXIV_QUERY = os.getenv(
    "ARXIV_QUERY",
    "(ti:SerDes OR ti:\"serial link\" OR ti:transceiver) AND "
    "(ti:CDR OR ti:equalization OR ti:DFE OR ti:FFE OR ti:CTLE OR "
    "ti:PAM4 OR ti:\"112G\" OR ti:\"224G\" OR ti:\"high speed\")"
)

# IEEE Xplore: Boolean full-text search — most effective with OR/AND operators
# Targets actual circuit/system papers in JSSC, ISSCC, CICC, TCAS
IEEE_QUERY = os.getenv(
    "IEEE_QUERY",
    "(\"SerDes\" OR \"serial link\" OR \"high-speed transceiver\") AND "
    "(\"CDR\" OR \"clock and data recovery\" OR \"DFE\" OR \"FFE\" OR \"CTLE\" OR "
    "\"PAM4\" OR \"112Gbps\" OR \"224Gbps\" OR \"equalization\" OR "
    "\"ADC-based receiver\" OR \"bang-bang phase detector\")"
)

# Google Scholar: keyword-style, no Boolean — most natural language friendly
SCHOLAR_QUERY = os.getenv(
    "SCHOLAR_QUERY",
    "SerDes CDR equalization DFE FFE 112G 224G PAM4 transceiver ISSCC JSSC"
)

# Display label shown in email header
DISPLAY_QUERY = "SerDes · CDR · Equalization · PAM4 · 112G/224G"
# ───────────────────────────────────────────────────────────────────────────────


def fetch_arxiv(query: str = ARXIV_QUERY) -> list[dict]:
    # arXiv supports field-specific search: ti: abs: au: etc.
    url = (
        "https://export.arxiv.org/api/query"
        f"?search_query={requests.utils.quote(query)}"
        f"&start=0&max_results={MAX_RESULTS}"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        ns   = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)
        out  = []
        for e in root.findall("a:entry", ns):
            authors = [x.find("a:name", ns).text for x in e.findall("a:author", ns)[:3]]
            cats    = [c.get("term", "") for c in
                       e.findall("{http://arxiv.org/schemas/atom}category")][:2]
            out.append({
                "source":   "arXiv",
                "title":    e.find("a:title", ns).text.strip().replace("\n", " "),
                "link":     e.find("a:id", ns).text.strip(),
                "date":     e.find("a:published", ns).text[:10],
                "authors":  ", ".join(authors),
                "abstract": (e.find("a:summary", ns).text or "").strip().replace("\n", " ")[:380],
                "venue":    ", ".join(cats) or "cs/eess",
            })
        return out
    except Exception as ex:
        print(f"[arXiv] Error: {ex}")
        return []


def fetch_ieee(query: str = IEEE_QUERY) -> list[dict]:
    if not IEEE_KEY:
        print("[IEEE] No API key — skipping.")
        return []
    url = (
        "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        f"?querytext={requests.utils.quote(query)}"  # IEEE supports Boolean AND/OR
        f"&max_records={MAX_RESULTS}"
        "&sort_field=publication_year&sort_order=desc"
        f"&start_year={START_YEAR}"
        f"&apikey={IEEE_KEY}"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        data = r.json()
        out  = []
        for a in data.get("articles", []):
            authors = [x["full_name"] for x in
                       (a.get("authors") or {}).get("authors", [])[:3]]
            link = (a.get("html_url") or
                    (f"https://doi.org/{a['doi']}" if a.get("doi") else ""))
            out.append({
                "source":   "IEEE Xplore",
                "title":    a.get("title", "").strip(),
                "link":     link,
                "date":     str(a.get("publication_year", "")),
                "authors":  ", ".join(authors),
                "abstract": (a.get("abstract", "") or "").strip()[:380],
                "venue":    a.get("publication_title", ""),
            })
        return out
    except Exception as ex:
        print(f"[IEEE] Error: {ex}")
        return []


def fetch_scholar(query: str = SCHOLAR_QUERY) -> list[dict]:
    """
    Fetches Google Scholar results via SerpAPI.
    Sign up free at https://serpapi.com — 100 searches/month on the free tier.
    Add SERPAPI_KEY as a GitHub Secret to enable this source.
    """
    if not SERPAPI_KEY:
        print("[Scholar] No SERPAPI_KEY — skipping.")
        return []

    url = "https://serpapi.com/search"
    params = {
        "engine":   "google_scholar",
        "q":        query,
        "num":      MAX_RESULTS,
        "as_ylo":   START_YEAR,          # results from start year onwards
        "sort":     "date",              # most recent first
        "api_key":  SERPAPI_KEY,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        out  = []
        for item in data.get("organic_results", []):
            # Publication info block
            pub_info = item.get("publication_info", {})
            authors_raw = pub_info.get("authors", [])
            authors = ", ".join(a.get("name", "") for a in authors_raw[:3])
            if not authors:
                # fallback: parse from summary string e.g. "A Smith, B Jones - Nature, 2024"
                summary = pub_info.get("summary", "")
                authors = summary.split(" - ")[0].strip() if " - " in summary else ""

            # Date: try to extract year from summary
            summary  = pub_info.get("summary", "")
            date_str = ""
            for part in summary.split(","):
                part = part.strip()
                if part.isdigit() and len(part) == 4:
                    date_str = part
                    break

            # Venue: everything after " - " in summary
            venue = ""
            if " - " in summary:
                venue = summary.split(" - ", 1)[-1].strip()
                venue = venue[:60] + "…" if len(venue) > 60 else venue

            snippet  = (item.get("snippet") or "").strip()[:380]
            link     = item.get("link", "")

            out.append({
                "source":   "Google Scholar",
                "title":    item.get("title", "").strip(),
                "link":     link,
                "date":     date_str,
                "authors":  authors,
                "abstract": snippet,
                "venue":    venue,
            })
        return out
    except Exception as ex:
        print(f"[Scholar] Error: {ex}")
        return []


# ─── HTML EMAIL TEMPLATE ───────────────────────────────────────────────────────

def badge_html(source: str) -> str:
    styles = {
        "arXiv":          ("background:#dbeafe;color:#1d4ed8;", "arXiv"),
        "IEEE Xplore":    ("background:#dcfce7;color:#166534;", "IEEE"),
        "Google Scholar": ("background:#fef9c3;color:#854d0e;", "Scholar"),
    }
    bg, label = styles.get(source, ("background:#f3f4f6;color:#374151;", source))
    return (f'<span style="{bg}padding:2px 8px;border-radius:4px;'
            f'font-size:11px;font-weight:600;">{label}</span>')


def paper_row(p: dict) -> str:
    authors_str = p["authors"] + (" et al." if "," in p["authors"] else "")
    title_html  = (
        f'<a href="{p["link"]}" style="color:#1d4ed8;text-decoration:none;'
        f'font-size:14px;font-weight:600;line-height:1.5;">{p["title"]}</a>'
        if p["link"] else
        f'<span style="font-size:14px;font-weight:600;line-height:1.5;">{p["title"]}</span>'
    )
    venue_short = p["venue"][:45] + "…" if len(p["venue"]) > 45 else p["venue"]
    return f"""
    <tr>
      <td style="padding:16px 20px;border-bottom:1px solid #f0f0f0;vertical-align:top;">
        <div style="margin-bottom:6px;">{title_html}</div>
        <div style="font-size:12px;color:#6b7280;margin-bottom:8px;flex-wrap:wrap;">
          <span>👤 {authors_str}</span>
          &nbsp;·&nbsp;
          <span>📅 {p["date"]}</span>
          &nbsp;·&nbsp;
          <span>{venue_short}</span>
          &nbsp;&nbsp;{badge_html(p["source"])}
        </div>
        <div style="font-size:13px;color:#374151;line-height:1.65;">
          {p["abstract"]}{"…" if len(p["abstract"]) >= 379 else ""}
        </div>
      </td>
    </tr>"""


def section_header(title: str, count: int, color: str) -> str:
    return f"""
    <tr>
      <td style="padding:20px 20px 8px;background:#f8fafc;">
        <span style="font-size:13px;font-weight:700;color:{color};text-transform:uppercase;
                     letter-spacing:0.05em;">{title}</span>
        <span style="background:{color}22;color:{color};border-radius:20px;
                     padding:2px 10px;font-size:12px;font-weight:600;margin-left:8px;">{count}</span>
      </td>
    </tr>"""


def build_email_html(
    arxiv: list[dict],
    ieee: list[dict],
    scholar: list[dict],
    query: str = DISPLAY_QUERY,
) -> str:
    date_str = datetime.now().strftime("%A, %d %B %Y")
    total    = len(arxiv) + len(ieee) + len(scholar)

    arxiv_rows = (
        "".join(paper_row(p) for p in arxiv)
        if arxiv else
        '<tr><td style="padding:16px 20px;color:#9ca3af;font-size:13px;">No arXiv results found today.</td></tr>'
    )
    ieee_rows = (
        "".join(paper_row(p) for p in ieee)
        if ieee else
        '<tr><td style="padding:16px 20px;color:#9ca3af;font-size:13px;">No IEEE results — add IEEE_API_KEY secret to enable.</td></tr>'
    )
    scholar_rows = (
        "".join(paper_row(p) for p in scholar)
        if scholar else
        '<tr><td style="padding:16px 20px;color:#9ca3af;font-size:13px;">No Scholar results — add SERPAPI_KEY secret to enable.</td></tr>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>SerDes Digest — {date_str}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:24px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;">

  <!-- Header -->
  <tr>
    <td style="background:#1e3a5f;border-radius:12px 12px 0 0;padding:28px 28px 22px;">
      <div style="font-size:22px;font-weight:700;color:#ffffff;margin-bottom:4px;">
        📡 SerDes Daily Digest
      </div>
      <div style="font-size:13px;color:#93c5fd;">{date_str}</div>
      <div style="margin-top:14px;">
        <span style="background:#ffffff22;color:#e0f2fe;border-radius:20px;
                     padding:4px 14px;font-size:12px;">🔍 {query}</span>
        &nbsp;
        <span style="background:#ffffff22;color:#e0f2fe;border-radius:20px;
                     padding:4px 14px;font-size:12px;">📄 {total} papers</span>
      </div>
    </td>
  </tr>

  <!-- Body -->
  <tr>
    <td style="background:#ffffff;">
      <table width="100%" cellpadding="0" cellspacing="0">

        {section_header("📚 arXiv Papers", len(arxiv), "#1d4ed8")}
        {arxiv_rows}

        {section_header("📡 IEEE Xplore Papers", len(ieee), "#166534")}
        {ieee_rows}

        {section_header("🎓 Google Scholar Papers", len(scholar), "#854d0e")}
        {scholar_rows}

      </table>
    </td>
  </tr>

  <!-- Footer -->
  <tr>
    <td style="background:#f8fafc;border-top:1px solid #e5e7eb;border-radius:0 0 12px 12px;
               padding:16px 20px;text-align:center;">
      <p style="font-size:11px;color:#9ca3af;margin:0;">
        Auto-generated by <strong>serdes-digest</strong> via GitHub Actions
        &nbsp;·&nbsp; Sources: arXiv API, IEEE Xplore API, Google Scholar (SerpAPI)
        &nbsp;·&nbsp; To unsubscribe, remove DIGEST_EMAIL from GitHub repo variables.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body></html>"""


# ─── SEND VIA RESEND ──────────────────────────────────────────────────────────

def send_email(html_body: str, total: int) -> bool:
    if not RESEND_KEY:
        print("[email] No RESEND_API_KEY set — skipping email.")
        return False
    if not DIGEST_EMAIL:
        print("[email] No DIGEST_EMAIL set — skipping email.")
        return False

    recipients = [e.strip() for e in DIGEST_EMAIL.split(",") if e.strip()]
    date_str   = datetime.now().strftime("%d %b %Y")
    payload    = {
        "from":    FROM_EMAIL,
        "to":      recipients,
        "subject": f"📡 SerDes Digest — {total} papers — {date_str}",
        "html":    html_body,
    }
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_KEY}",
                "Content-Type":  "application/json",
            },
            data=json.dumps(payload),
            timeout=30,
        )
        if r.status_code in (200, 201):
            print(f"[email] ✓ Sent to {len(recipients)} recipient(s): {', '.join(recipients)} "
                  f"(id: {r.json().get('id', '')})")
            return True
        else:
            print(f"[email] ✗ Failed — HTTP {r.status_code}: {r.text}")
            return False
    except Exception as ex:
        print(f"[email] Error: {ex}")
        return False


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"[run] arXiv query  : {ARXIV_QUERY[:80]}...")
    print(f"[run] IEEE query   : {IEEE_QUERY[:80]}...")
    print(f"[run] Scholar query: {SCHOLAR_QUERY}")
    print(f"[run] To email     : {DIGEST_EMAIL or 'NOT SET'}")
    print(f"[run] Resend key   : {'set ✓' if RESEND_KEY else 'NOT SET'}")
    print(f"[run] IEEE key     : {'set ✓' if IEEE_KEY else 'not set (optional)'}")
    print(f"[run] SerpAPI key  : {'set ✓' if SERPAPI_KEY else 'not set (optional)'}")

    arxiv_papers   = fetch_arxiv()
    print(f"[arXiv]   {len(arxiv_papers)} papers fetched")

    ieee_papers    = fetch_ieee()
    print(f"[IEEE]    {len(ieee_papers)} papers fetched")

    scholar_papers = fetch_scholar()
    print(f"[Scholar] {len(scholar_papers)} papers fetched")

    total     = len(arxiv_papers) + len(ieee_papers) + len(scholar_papers)
    html_body = build_email_html(arxiv_papers, ieee_papers, scholar_papers)

    # Save local copy for debugging
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_body)
    print("[run] index.html saved (local preview)")

    send_email(html_body, total)
    print("[run] Done.")
