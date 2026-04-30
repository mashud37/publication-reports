import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _smtp_config():
    return {
        "host": os.environ["SMTP_HOST"],
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ["SMTP_USER"],
        "password": os.environ["SMTP_PASS"],
        "to": os.environ["EMAIL_TO"],
    }


def _send(msg):
    cfg = _smtp_config()
    msg["From"] = cfg["user"]
    msg["To"] = cfg["to"]
    with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
        server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    print(f"Email sent: {msg['Subject']}")


def send_weekly_email(week_date, ranked, access_token):
    base_url = os.environ["BASE_URL"]
    url = f"{base_url}/week/{week_date}?token={access_token}"
    total = len(ranked)
    is_ranked = ranked and ranked[0][1] is not None

    groups = {}
    for article, _ in ranked:
        groups.setdefault(article["journal_group"], 0)
        groups[article["journal_group"]] += 1
    group_summary = " &nbsp;·&nbsp; ".join(
        f"{g} ({n})" for g, n in sorted(groups.items())
    )

    ranked_note = (
        "Articles are ranked by predicted relevance based on your past selections."
        if is_ranked
        else "Articles are not yet ranked. Make selections each week to train the model."
    )

    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:660px;margin:0 auto;padding:1.5rem;color:#111">
<h2 style="margin-bottom:0.3rem">Publications — Week of {week_date}</h2>
<p style="color:#6b7280;margin-top:0;font-size:0.9rem">{total} new publications</p>
<p style="color:#374151;font-size:0.88rem;margin-bottom:0.3rem">{group_summary}</p>
<p style="color:#6b7280;font-size:0.85rem;margin-top:0.2rem">{ranked_note}</p>
<p style="margin-top:1.5rem">
  <a href="{url}"
     style="display:inline-block;background:#2563eb;color:white;padding:0.65rem 1.6rem;
            text-decoration:none;border-radius:5px;font-weight:600;font-size:1rem">
    View &amp; Select Articles →
  </a>
</p>
<p style="color:#9ca3af;font-size:0.78rem;margin-top:2rem">
  After you make your selections, you will receive a follow-up email with the selected
  articles in a readable format and a Zotero-importable RIS file.
</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Publications — Week of {week_date} ({total} new)"
    msg.attach(MIMEText(html, "html"))
    _send(msg)


def _ris_record(article):
    lines = ["TY  - JOUR", f"TI  - {article['title']}"]
    for author in article["authors"].split("; "):
        if author.strip():
            lines.append(f"AU  - {author.strip()}")
    lines.append(f"JO  - {article['journal_name']}")
    if article["doi"]:
        lines.append(f"DO  - {article['doi']}")
        lines.append(f"UR  - https://doi.org/{article['doi']}")
    if article["abstract"]:
        lines.append(f"AB  - {article['abstract']}")
    lines.append("ER  - ")
    return "\n".join(lines)


def _markdown_report(week_date, articles):
    lines = [f"# Selected Publications — Week of {week_date}\n"]
    current_group = None
    for a in sorted(articles, key=lambda x: x["journal_group"]):
        if a["journal_group"] != current_group:
            current_group = a["journal_group"]
            lines.append(f"\n## {current_group}\n")
        lines.append(f"### {a['title']}")
        lines.append(f"{a['journal_name']} | {a['authors']}  ")
        lines.append(f"https://doi.org/{a['doi']}  \n")
        if a["abstract"]:
            lines.append(f"{a['abstract']}\n")
        lines.append("---\n")
    return "\n".join(lines)


def send_selection_email(week_date, articles):
    if not articles:
        return

    report_md = _markdown_report(week_date, articles)
    ris_content = "\n\n".join(_ris_record(a) for a in articles)
    doi_list = "\n".join(a["doi"] for a in articles if a["doi"])

    sorted_articles = sorted(articles, key=lambda x: x["journal_group"])

    article_cards = "".join(f"""
<div style="margin:1rem 0;padding:1rem;border:1px solid #e5e7eb;border-radius:6px">
  <strong>{a['title']}</strong><br>
  <span style="color:#6b7280;font-size:0.82em">{a['journal_name']} &nbsp;|&nbsp; {a['authors']}</span><br>
  <a href="https://doi.org/{a['doi']}" style="font-size:0.82em;color:#2563eb">doi.org/{a['doi']}</a>
  {"<p style='color:#374151;font-size:0.86em;margin-top:0.4em'>" + a['abstract'][:400] + ("…" if len(a['abstract']) > 400 else "") + "</p>" if a['abstract'] else ""}
</div>""" for a in sorted_articles)

    html_body = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:660px;margin:0 auto;padding:1.5rem;color:#111">
<h2>Your Selections — Week of {week_date}</h2>
<p style="color:#6b7280">{len(articles)} article{'s' if len(articles) != 1 else ''} selected.
Attachments: readable list (.md), Zotero RIS import (.ris), and DOI list (.txt).</p>

<h3 style="margin-bottom:0.4rem">Import into Zotero</h3>
<p style="color:#374151;font-size:0.88rem;margin-top:0">
  <strong>Option 1 — RIS file:</strong> File → Import → select <code>selections-{week_date}.ris</code><br>
  <strong>Option 2 — DOI lookup</strong> (captures full metadata): Tools → Add Items by Identifier,
  then paste the DOIs below:
</p>
<pre style="background:#f3f4f6;padding:0.75rem 1rem;border-radius:4px;font-size:0.85rem;line-height:1.7;overflow-x:auto">{doi_list}</pre>

<hr style="border:none;border-top:1px solid #e5e7eb;margin:1.5rem 0">
<h3 style="margin-bottom:0.5rem">Selected Articles</h3>
{article_cards}
<hr style="border:none;border-top:1px solid #e5e7eb;margin:1rem 0">
<p style="color:#9ca3af;font-size:0.78em">Publication Reports — automated weekly digest</p>
</body></html>"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Your selections — Week of {week_date} ({len(articles)} articles)"
    msg.attach(MIMEText(html_body, "html"))

    for filename, content, mimetype in [
        (f"selections-{week_date}.md", report_md, "text/markdown"),
        (f"selections-{week_date}.ris", ris_content, "application/x-research-info-systems"),
        (f"selections-{week_date}-dois.txt", doi_list, "text/plain"),
    ]:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(content.encode("utf-8"))
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=filename)
        part.add_header("Content-Type", mimetype)
        msg.attach(part)

    _send(msg)
