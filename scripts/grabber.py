import re
import requests
import pandas as pd


def fetch_articles(csv_path, filter_from, filter_to):
    info = pd.read_csv(csv_path)
    info_cr = info[info["crossref"] == "T"]

    filters = f"from-created-date:{filter_from},until-created-date:{filter_to}"
    attributes = "title,author,DOI,created,abstract"

    articles = []
    journals = list(info_cr.iterrows())
    total = len(journals)
    for i, (_, row) in enumerate(journals, 1):
        issn = row["o-issn"]
        print(f"[{i}/{total}] fetching {row['name']} ({issn})")
        url = (
            f"http://api.crossref.org/journals/{issn}/works"
            f"?select={attributes}&filter={filters}&rows=500"
        )
        try:
            response = requests.get(url, timeout=30)
        except requests.RequestException:
            continue
        if response.status_code != 200:
            continue

        for item in response.json().get("message", {}).get("items", []):
            title_parts = item.get("title", [])
            if not title_parts:
                continue
            title = re.sub(r"<[^>]+>", "", title_parts[0])
            title = re.sub(r"\s+", " ", title).strip()
            if not title:
                continue

            authors = "; ".join(
                f"{a.get('family', '')}, {a.get('given', '')}".strip(", ")
                for a in item.get("author", [])
                if a.get("family")
            )

            raw_abstract = item.get("abstract", "") or ""
            abstract = re.sub(r"<[^>]+>", "", raw_abstract)
            abstract = re.sub(r"\s+", " ", abstract).strip()

            articles.append({
                "doi": item.get("DOI", ""),
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "journal_name": row["name"],
                "journal_group": row["group"],
                "week_date": filter_from,
            })

    return articles
