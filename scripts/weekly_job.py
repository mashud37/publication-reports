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
    sunday = monday + timedelta(days=6)
    return monday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")


def run():
    init_db()

    if os.path.exists(HISTORICAL_CSV):
        load_historical(HISTORICAL_CSV)

    filter_from, filter_to = week_dates()

    if not get_week_articles(filter_from):
        print(f"Fetching {filter_from} → {filter_to}")
        articles = fetch_articles(CSV_PATH, filter_from, filter_to)
        save_articles(articles)
        print(f"Saved {len(articles)} articles")

    articles = get_week_articles(filter_from)
    ranked = rank(articles)
    send_weekly_email(filter_from, ranked, access_token=os.environ["ACCESS_TOKEN"])


if __name__ == "__main__":
    run()
