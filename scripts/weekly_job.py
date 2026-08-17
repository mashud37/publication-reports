import os
from datetime import datetime, timedelta
from db import init_db, load_historical, save_articles, get_week_articles
from grabber import fetch_articles
from ranker import rank
from emailer import send_weekly_email

CSV_PATH = os.environ.get("CSV_PATH", "info/journal-info-comb.csv")
HISTORICAL_CSV = os.environ.get("HISTORICAL_CSV", "model/data/asreview_labels.csv")


def week_dates():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    last_monday = monday - timedelta(days=7)
    return {
        "week_label": monday.strftime("%Y-%m-%d"),
        "fetch_from": last_monday.strftime("%Y-%m-%d"),
        "fetch_to": monday.strftime("%Y-%m-%d"),
    }


def run():
    print("weekly job: starting")
    print("  · 1/4  Init DB")
    print("  · 2/4  Fetch articles from CrossRef")
    print("  · 3/4  Rank articles")
    print("  · 4/4  Send email")

    print("weekly job [1/4] init DB")
    init_db()

    if os.path.exists(HISTORICAL_CSV):
        print(f"weekly job: loading historical labels from {HISTORICAL_CSV}")
        load_historical(HISTORICAL_CSV)

    dates = week_dates()
    week_label, fetch_from, fetch_to = dates["week_label"], dates["fetch_from"], dates["fetch_to"]

    if not get_week_articles(week_label):
        print(f"weekly job [2/4] fetching {fetch_from} → {fetch_to}")
        articles = fetch_articles(CSV_PATH, fetch_from, fetch_to)
        for a in articles:
            a["week_date"] = week_label
        save_articles(articles)
        print(f"Saved {len(articles)} articles")
    else:
        print(f"weekly job [2/4] using cached articles for {week_label}")

    articles = get_week_articles(week_label)
    print(f"weekly job [3/4] ranking {len(articles)} articles")
    ranked = rank(articles)
    print(f"weekly job [4/4] sending email for week {week_label}")
    send_weekly_email(week_label, ranked, access_token=os.environ["ACCESS_TOKEN"])


if __name__ == "__main__":
    run()
