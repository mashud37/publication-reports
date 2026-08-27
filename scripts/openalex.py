"""Fill in article abstracts from OpenAlex when CrossRef returns none. Feeds the weekly ranking model and the selection page."""

import os
import time
import requests

# ---- Settings ----

API_URL = "https://api.openalex.org/works"

DEFAULTS = {
    "batch_size": 50,
    "min_words": 20,
    "timeout": 60,
    "pause_seconds": 0.2,
}

REJECT_PHRASES = [
    "data sharing not applicable",
    "the author declares",
    "the authors declare",
    "no abstract is available",
    "no abstract available",
]


def request_params(dois):
    params = {
        "filter": "doi:" + "|".join(dois),
        "select": "doi,abstract_inverted_index",
        "per-page": DEFAULTS["batch_size"],
    }
    mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if mailto:
        params["mailto"] = mailto
    if api_key:
        params["api_key"] = api_key
    return params


def rebuild_abstract(inverted_index):
    if not inverted_index:
        return ""
    slots = []
    for word, positions in inverted_index.items():
        for position in positions:
            slots.append((position, word))
    slots.sort()
    words = [word for _, word in slots]
    return " ".join(words)


def looks_like_abstract(text):
    if len(text.split()) < DEFAULTS["min_words"]:
        return False
    lowered = text.lower()
    if lowered.startswith("article title:"):
        return False
    if "journal name:" in lowered and "authors:" in lowered:
        return False
    opening = lowered[:120]
    for phrase in REJECT_PHRASES:
        if phrase in opening:
            return False
    return True


def articles_missing_abstracts(articles):
    missing = []
    for article in articles:
        abstract = (article.get("abstract") or "").strip()
        doi = (article.get("doi") or "").strip()
        if not abstract and doi:
            missing.append(article)
    return missing


def read_batch(dois):
    response = requests.get(API_URL, params=request_params(dois), timeout=DEFAULTS["timeout"])
    if response.status_code != 200:
        raise RuntimeError(f"OpenAlex returned status {response.status_code}")

    found = {}
    rejected = 0
    for work in response.json().get("results", []):
        doi = (work.get("doi") or "").replace("https://doi.org/", "").strip().lower()
        abstract = rebuild_abstract(work.get("abstract_inverted_index"))
        if not doi or not abstract:
            continue
        if looks_like_abstract(abstract):
            found[doi] = abstract
        else:
            rejected += 1
    return {"found": found, "rejected": rejected}


def fill_missing_abstracts(articles):
    missing = articles_missing_abstracts(articles)
    result = {
        "checked": len(missing),
        "filled": 0,
        "rejected": 0,
        "failed": 0,
        "updates": [],
    }
    if not missing:
        print("OpenAlex: no articles are missing an abstract")
        return result

    size = DEFAULTS["batch_size"]
    batches = [missing[i:i + size] for i in range(0, len(missing), size)]
    total = len(batches)
    print(f"OpenAlex: looking up {len(missing)} articles ({total} batches)")

    for number, batch in enumerate(batches, 1):
        dois = [article["doi"].strip().lower() for article in batch]
        print(f"[{number}/{total}] OpenAlex lookup for {len(dois)} DOIs")
        try:
            batch_result = read_batch(dois)
        except (requests.RequestException, RuntimeError, ValueError) as error:
            print(f"  batch failed: {error}")
            result["failed"] += len(batch)
            continue

        result["rejected"] += batch_result["rejected"]
        for article in batch:
            abstract = batch_result["found"].get(article["doi"].strip().lower())
            if not abstract:
                continue
            article["abstract"] = abstract
            result["updates"].append({"doi": article["doi"], "abstract": abstract})
            result["filled"] += 1
        time.sleep(DEFAULTS["pause_seconds"])

    print(f"OpenAlex: filled {result['filled']} of {result['checked']} missing abstracts")
    if result["rejected"]:
        print(f"OpenAlex: discarded {result['rejected']} entries that were not abstracts")
    if result["failed"]:
        print(f"OpenAlex: {result['failed']} articles could not be looked up")
    return result
