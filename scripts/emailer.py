import copy
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _send(msg):
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASS"]

    outgoing = copy.deepcopy(msg)
    outgoing["From"] = user
    outgoing["To"] = os.environ["EMAIL_TO"]
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(outgoing)
    print(f"Email sent: {outgoing['Subject']}")


def send_weekly_email(week_date, ranked, access_token):
    base_url = os.environ["BASE_URL"]
    url = f"{base_url}/week/{week_date}?token={access_token}"
    total = len(ranked)
    is_ranked = ranked and ranked[0][1] is not None

    groups = {}
    for article, _ in ranked:
        groups.setdefault(article["journal_group"], 0)
        groups[article["journal_group"]] += 1
    group_lines = "\n".join(f"  {g}: {n}" for g, n in sorted(groups.items()))

    ranked_note = (
        "Ranked by predicted relevance."
        if is_ranked
        else "Not yet ranked, make selections each week to train the model."
    )

    body = f"""Publications: Week of {week_date}
{total} new publications

{group_lines}

{ranked_note}

{url}"""

    msg = MIMEText(body, "plain")
    msg["Subject"] = f"Publications: Week of {week_date} ({total} new)"
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
    lines = [f"# Selected Publications: Week of {week_date}\n"]
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

    article_lines = []
    for a in sorted_articles:
        article_lines.append(a["title"])
        article_lines.append(f"{a['journal_name']} | {a['authors']}")
        if a["doi"]:
            article_lines.append(f"https://doi.org/{a['doi']}")
        article_lines.append("")

    article_block = "\n".join(article_lines)
    plural = "s" if len(articles) != 1 else ""

    body = f"""Your selections - Week of {week_date}
{len(articles)} article{plural} selected

{article_block}
DOIs:
{doi_list}

Attachments: .md readable list, .ris Zotero import, -dois.txt plain DOI list"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = f"Your selections: Week of {week_date} ({len(articles)} articles)"
    msg.attach(MIMEText(body, "plain"))

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
